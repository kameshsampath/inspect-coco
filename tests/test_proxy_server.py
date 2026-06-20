"""Tests for the OAuth token proxy server (host-process mode)."""

from __future__ import annotations

import json
import time
from threading import Thread
from unittest.mock import patch
from urllib.request import Request, urlopen

import pytest

from inspect_coco.proxy.server import (
    ProxyServer,
    TokenProxy,
    TokenState,
)


@pytest.fixture
def mock_keyring_tokens(monkeypatch):
    """Mock keyring to return valid tokens."""
    from inspect_coco.config.oauth import OAuthTokens

    tokens = OAuthTokens(
        access_token="test-at",
        refresh_token="test-rt",
        expires_at=time.time() + 600,
        account="test-account",
        role="ANALYST",
    )

    with patch("inspect_coco.config.oauth.load_cached_tokens", return_value=tokens):
        yield tokens


@pytest.fixture
def mock_keyring_no_tokens(monkeypatch):
    """Mock keyring with no tokens."""
    with patch("inspect_coco.config.oauth.load_cached_tokens", return_value=None):
        yield


class TestTokenState:
    def test_has_tokens_when_cached(self, mock_keyring_tokens):
        state = TokenState(account="test-account")
        assert state.has_tokens

    def test_no_tokens_when_empty(self, mock_keyring_no_tokens):
        state = TokenState(account="test-account")
        assert not state.has_tokens

    def test_get_access_token_returns_valid(self, mock_keyring_tokens):
        state = TokenState(account="test-account")
        result = state.get_access_token()
        assert result["access_token"] == "test-at"
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] > 0

    @patch("inspect_coco.config.oauth.get_valid_token")
    @patch("inspect_coco.config.oauth.load_cached_tokens")
    def test_refreshes_expired_token(self, mock_load, mock_refresh):
        from inspect_coco.config.oauth import OAuthTokens

        expired = OAuthTokens(
            access_token="old-at",
            refresh_token="rt",
            expires_at=time.time() - 100,
            account="test-account",
        )
        refreshed = OAuthTokens(
            access_token="new-at",
            refresh_token="rt",
            expires_at=time.time() + 600,
            account="test-account",
        )
        mock_load.return_value = expired
        mock_refresh.return_value = refreshed

        state = TokenState(account="test-account")
        result = state.get_access_token()
        assert result["access_token"] == "new-at"


class TestProxyServer:
    @pytest.fixture
    def running_proxy(self, mock_keyring_tokens):
        """Start a proxy server and yield the base URL."""
        state = TokenState(account="test-account")
        server = ProxyServer(token_state=state)
        port = server.port
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()

    def test_random_port_assignment(self, mock_keyring_tokens):
        state = TokenState(account="test-account")
        server = ProxyServer(token_state=state)
        assert server.port > 0
        assert server.port != 8765  # Should be random, not default
        server.server_close()

    def test_get_token(self, running_proxy):
        resp = urlopen(Request(f"{running_proxy}/token"))
        data = json.loads(resp.read())
        assert "access_token" in data
        assert data["token_type"] == "Bearer"

    def test_get_health(self, running_proxy):
        resp = urlopen(Request(f"{running_proxy}/health"))
        data = json.loads(resp.read())
        assert data["status"] == "ok"

    def test_not_found(self, running_proxy):
        from urllib.error import HTTPError

        with pytest.raises(HTTPError) as exc_info:
            urlopen(Request(f"{running_proxy}/nonexistent"))
        assert exc_info.value.code == 404

    def test_no_tokens_returns_503(self, mock_keyring_no_tokens):
        from urllib.error import HTTPError

        state = TokenState(account="test-account")
        server = ProxyServer(token_state=state)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with pytest.raises(HTTPError) as exc_info:
                urlopen(Request(f"http://127.0.0.1:{server.port}/token"))
            assert exc_info.value.code == 503
        finally:
            server.shutdown()


class TestTokenProxy:
    def test_lifecycle(self, mock_keyring_tokens):
        proxy = TokenProxy(account="test-account")
        proxy.start()
        assert proxy.port > 0
        # Verify it serves
        resp = urlopen(Request(f"{proxy.url}/health"))
        data = json.loads(resp.read())
        assert data["status"] == "ok"
        proxy.stop()

    def test_context_manager(self, mock_keyring_tokens):
        with TokenProxy(account="test-account") as proxy:
            resp = urlopen(Request(f"{proxy.url}/token"))
            data = json.loads(resp.read())
            assert data["access_token"] == "test-at"
