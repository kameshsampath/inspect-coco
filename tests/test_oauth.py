"""Tests for the OAuth module."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from inspect_coco.config.oauth import (
    OAuthError,
    OAuthTokens,
    _normalize_account,
    _oauth_scope,
    clear_cached_tokens,
    generate_pkce,
    get_valid_token,
    load_cached_tokens,
    save_cached_tokens,
)


@pytest.fixture
def sf_home(tmp_path, monkeypatch):
    """Set SNOWFLAKE_HOME to a temp directory."""
    monkeypatch.setenv("SNOWFLAKE_HOME", str(tmp_path))
    return tmp_path


class TestPkce:
    def test_generate_pkce_produces_valid_pair(self):
        pkce = generate_pkce()
        assert len(pkce.verifier) == 64
        assert len(pkce.challenge) > 0
        assert pkce.verifier != pkce.challenge

    def test_generate_pkce_unique_each_call(self):
        a = generate_pkce()
        b = generate_pkce()
        assert a.verifier != b.verifier


class TestOAuthTokens:
    def test_not_expired(self):
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() + 600,
            account="org-acct",
        )
        assert not tokens.is_expired

    def test_expired(self):
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() - 1,
            account="org-acct",
        )
        assert tokens.is_expired

    def test_expired_within_skew(self):
        # Expires in 60s but skew is 120s, so considered expired
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() + 60,
            account="org-acct",
        )
        assert tokens.is_expired

    def test_round_trip(self):
        original = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=1234567890.0,
            account="org-acct",
            role="ANALYST",
        )
        restored = OAuthTokens.from_dict(original.to_dict())
        assert restored.access_token == "at"
        assert restored.refresh_token == "rt"
        assert restored.expires_at == 1234567890.0
        assert restored.account == "org-acct"
        assert restored.role == "ANALYST"


class TestTokenCache:
    """Tests for file-based token cache (fallback when keyring unavailable)."""

    def test_save_and_load(self, sf_home: Path):
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() + 600,
            account="org-acct",
            role="SYSADMIN",
        )
        save_cached_tokens(tokens)
        loaded = load_cached_tokens(account="org-acct")
        assert loaded is not None
        assert loaded.access_token == "at"
        assert loaded.refresh_token == "rt"
        assert loaded.account == "org-acct"
        assert loaded.role == "SYSADMIN"

    def test_load_returns_none_when_missing(self, sf_home: Path):
        assert load_cached_tokens() is None

    def test_load_returns_none_on_invalid_json(self, sf_home: Path):
        cache_path = sf_home / "inspect-coco-oauth.json"
        cache_path.write_text("not valid json{{{")
        assert load_cached_tokens() is None

    def test_load_returns_none_on_missing_keys(self, sf_home: Path):
        cache_path = sf_home / "inspect-coco-oauth.json"
        cache_path.write_text(json.dumps({"access_token": "at"}))
        assert load_cached_tokens() is None

    def test_clear_existing(self, sf_home: Path):
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() + 600,
            account="org-acct",
        )
        save_cached_tokens(tokens)
        assert clear_cached_tokens() is True
        assert load_cached_tokens() is None

    def test_clear_nonexistent(self, sf_home: Path):
        assert clear_cached_tokens() is False

    def test_save_sets_permissions(self, sf_home: Path):
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() + 600,
            account="org-acct",
        )
        save_cached_tokens(tokens)
        cache_path = sf_home / "inspect-coco-oauth.json"
        assert cache_path.stat().st_mode & 0o777 == 0o600


class TestNormalizeAccount:
    def test_plain_account(self):
        assert _normalize_account("myorg-myaccount") == "myorg-myaccount"

    def test_strips_domain(self):
        assert _normalize_account("myorg-myaccount.snowflakecomputing.com") == "myorg-myaccount"

    def test_strips_url(self):
        assert (
            _normalize_account("https://myorg-myaccount.snowflakecomputing.com")
            == "myorg-myaccount"
        )

    def test_strips_trailing_slash(self):
        assert _normalize_account("myorg-myaccount/") == "myorg-myaccount"


class TestOAuthScope:
    def test_no_role(self):
        assert _oauth_scope(None) == "refresh_token"

    def test_simple_role(self):
        assert _oauth_scope("SYSADMIN") == "refresh_token session:role:SYSADMIN"

    def test_role_with_special_chars(self):
        scope = _oauth_scope("my role")
        assert "session:role-encoded:" in scope


class TestGetValidToken:
    def test_returns_unexpired_token_unchanged(self):
        tokens = OAuthTokens(
            access_token="at",
            refresh_token="rt",
            expires_at=time.time() + 600,
            account="org-acct",
        )
        result = get_valid_token(tokens)
        assert result is tokens

    @patch("inspect_coco.config.oauth.refresh_access_token")
    @patch("inspect_coco.config.oauth.save_cached_tokens")
    def test_refreshes_expired_token(self, mock_save, mock_refresh, sf_home: Path):
        mock_refresh.return_value = {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "expires_in": 600,
        }
        tokens = OAuthTokens(
            access_token="old-at",
            refresh_token="rt",
            expires_at=time.time() - 1,
            account="org-acct",
            role="ANALYST",
        )
        result = get_valid_token(tokens)
        assert result.access_token == "new-at"
        assert result.refresh_token == "new-rt"
        assert result.role == "ANALYST"
        mock_refresh.assert_called_once_with("org-acct", "rt")
        mock_save.assert_called_once()

    @patch("inspect_coco.config.oauth.refresh_access_token")
    def test_refresh_failure_raises(self, mock_refresh, sf_home: Path):
        mock_refresh.side_effect = OAuthError("refresh failed")
        tokens = OAuthTokens(
            access_token="old-at",
            refresh_token="rt",
            expires_at=time.time() - 1,
            account="org-acct",
        )
        with pytest.raises(OAuthError, match="refresh failed"):
            get_valid_token(tokens)
