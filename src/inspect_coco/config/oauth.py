"""Snowflake Local OAuth flow using SNOWFLAKE$LOCAL_APPLICATION.

Implements the OAuth Authorization Code flow with PKCE for local development.
The host machine handles the browser interaction and token management.
Containers receive only short-lived access tokens via the token proxy.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
import webbrowser
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from inspect_coco.config.connection import snowflake_home

logger = logging.getLogger(__name__)

OAUTH_CLIENT_ID = "LOCAL_APPLICATION"
OAUTH_CALLBACK_HOST = "127.0.0.1"
OAUTH_TIMEOUT_SEC = 300
ACCESS_TOKEN_REFRESH_SKEW_SEC = 120
TOKEN_CACHE_FILE = "inspect-coco-oauth.json"


@dataclass
class OAuthTokens:
    """Cached OAuth tokens."""

    access_token: str
    refresh_token: str
    expires_at: float
    account: str
    role: str | None = None

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at - ACCESS_TOKEN_REFRESH_SKEW_SEC)

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "account": self.account,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict) -> OAuthTokens:
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            account=data["account"],
            role=data.get("role"),
        )


@dataclass
class PkceCodes:
    """PKCE verifier and challenge pair."""

    verifier: str
    challenge: str


def generate_pkce() -> PkceCodes:
    """Generate a PKCE code verifier and S256 challenge."""
    verifier = secrets.token_urlsafe(64)[:64]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkceCodes(verifier=verifier, challenge=challenge)


def _keyring_service(account: str) -> str:
    """Keyring service name for a given Snowflake account."""
    return f"{account}.inspect-coco"


def _use_keyring() -> bool:
    """Check whether the system keyring is available."""
    try:
        import keyring
        import keyring.errors
    except ImportError:
        return False

    try:
        keyring.get_credential("inspect-coco.probe", "test")
        return True
    except keyring.errors.NoKeyringError:
        return False
    except Exception:
        return False


def load_cached_tokens(account: str | None = None) -> OAuthTokens | None:
    """Load cached tokens from OS keyring (preferred) or file fallback."""
    if account:
        account = _normalize_account(account)
    if _use_keyring():
        return _load_from_keyring(account)
    tokens = _load_from_file()
    if tokens and account and tokens.account != account:
        return None
    return tokens


def save_cached_tokens(tokens: OAuthTokens) -> None:
    """Save tokens to OS keyring (preferred) or file fallback."""
    if _use_keyring():
        _save_to_keyring(tokens)
    else:
        logger.warning("Keyring unavailable, falling back to file-based token cache")
        _save_to_file(tokens)


def clear_cached_tokens(account: str | None = None) -> bool:
    """Remove cached tokens. Returns True if tokens were found and removed."""
    if _use_keyring():
        return _clear_from_keyring(account)
    return _clear_from_file()


# --- Keyring backend ---


def _load_from_keyring(account: str | None = None) -> OAuthTokens | None:
    """Load tokens from the OS keyring."""
    import keyring

    if account:
        service = _keyring_service(account)
        data_str = keyring.get_password(service, "refresh_token")
        if not data_str:
            return None
        meta_str = keyring.get_password(service, "token_metadata")
        if not meta_str:
            return None
        try:
            meta = json.loads(meta_str)
            return OAuthTokens(
                access_token=meta.get("access_token", ""),
                refresh_token=data_str,
                expires_at=meta.get("expires_at", 0.0),
                account=account,
                role=meta.get("role"),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    # No account specified — scan for any stored token
    # Check the file fallback for the account hint
    file_tokens = _load_from_file()
    if file_tokens:
        return file_tokens
    return None


def _save_to_keyring(tokens: OAuthTokens) -> None:
    """Save tokens to the OS keyring."""
    import keyring

    service = _keyring_service(tokens.account)
    keyring.set_password(service, "refresh_token", tokens.refresh_token)
    meta = json.dumps(
        {
            "access_token": tokens.access_token,
            "expires_at": tokens.expires_at,
            "role": tokens.role,
        }
    )
    keyring.set_password(service, "token_metadata", meta)


def _clear_from_keyring(account: str | None = None) -> bool:
    """Remove tokens from the OS keyring."""
    import keyring

    if not account:
        # Try to find account from file cache
        file_tokens = _load_from_file()
        if file_tokens:
            account = file_tokens.account
        if not account:
            return False

    service = _keyring_service(account)
    try:
        keyring.delete_password(service, "refresh_token")
        keyring.delete_password(service, "token_metadata")
        return True
    except Exception:
        return False


# --- File fallback (for CI/headless environments) ---


def _token_cache_path() -> Path:
    """Path to the OAuth token cache file."""
    return snowflake_home() / TOKEN_CACHE_FILE


def _load_from_file() -> OAuthTokens | None:
    """Load cached tokens from disk file."""
    path = _token_cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return OAuthTokens.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Invalid OAuth token cache file, ignoring")
        return None


def _save_to_file(tokens: OAuthTokens) -> None:
    """Save tokens to disk with restricted permissions."""
    path = _token_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens.to_dict(), indent=2))
    path.chmod(0o600)


def _clear_from_file() -> bool:
    """Remove cached token file."""
    path = _token_cache_path()
    if path.exists():
        path.unlink()
        return True
    return False


def _normalize_account(account: str) -> str:
    """Normalize account identifier for use in Snowflake URLs.

    Handles: protocol stripping, domain suffix removal, underscore-to-hyphen
    conversion (Snowflake URLs use hyphens, but some configs use underscores).
    """
    account = account.strip()
    if account.startswith("http"):
        account = urlparse(account).hostname or account
    account = account.removesuffix(".snowflakecomputing.com")
    account = account.rstrip("/")
    account = account.replace("_", "-")
    return account


def _oauth_scope(role: str | None) -> str:
    """Build OAuth scope string with optional role."""
    if not role:
        return "refresh_token"
    if all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in role):
        return f"refresh_token session:role:{role}"
    from urllib.parse import quote

    return f"refresh_token session:role-encoded:{quote(role)}"


def _build_authorize_url(
    account: str,
    role: str | None,
    state: str,
    pkce: PkceCodes,
    redirect_uri: str,
) -> str:
    """Build the Snowflake OAuth authorize URL."""
    params = urlencode(
        {
            "client_id": OAUTH_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": _oauth_scope(role),
            "state": state,
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"https://{account}.snowflakecomputing.com/oauth/authorize?{params}"


def exchange_code_for_tokens(account: str, code: str, pkce: PkceCodes, redirect_uri: str) -> dict:
    """Exchange an authorization code for access and refresh tokens."""
    url = f"https://{account}.snowflakecomputing.com/oauth/token-request"
    response = requests.post(
        url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": OAUTH_CLIENT_ID,
            "code_verifier": pkce.verifier,
        },
        auth=(OAUTH_CLIENT_ID, OAUTH_CLIENT_ID),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    if not response.ok:
        raise OAuthError(f"Token exchange failed ({response.status_code}): {response.text}")

    data = response.json()
    if "access_token" not in data:
        raise OAuthError("Token response missing access_token")
    if "refresh_token" not in data:
        raise OAuthError(
            "Token response missing refresh_token. "
            "Ensure the SNOWFLAKE$LOCAL_APPLICATION integration issues refresh tokens."
        )
    return data


def refresh_access_token(account: str, refresh_token: str) -> dict:
    """Use a refresh token to obtain a new access token."""
    url = f"https://{account}.snowflakecomputing.com/oauth/token-request"
    response = requests.post(
        url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
        },
        auth=(OAUTH_CLIENT_ID, OAUTH_CLIENT_ID),
        headers={"Accept": "application/json"},
        timeout=30,
    )

    if not response.ok:
        raise OAuthError(f"Token refresh failed ({response.status_code}): {response.text}")

    data = response.json()
    if "access_token" not in data:
        raise OAuthError("Refresh response missing access_token")
    return data


def get_valid_token(tokens: OAuthTokens) -> OAuthTokens:
    """Return tokens with a valid (non-expired) access token, refreshing if needed."""
    if not tokens.is_expired:
        return tokens

    logger.info("Access token expired, refreshing...")
    data = refresh_access_token(tokens.account, tokens.refresh_token)

    updated = OAuthTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", tokens.refresh_token),
        expires_at=time.time() + data.get("expires_in", 600),
        account=tokens.account,
        role=tokens.role,
    )
    save_cached_tokens(updated)
    return updated


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback."""

    server: _OAuthCallbackServer  # type: ignore[assignment]

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        state = params.get("state", [None])[0]
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]
        error_desc = params.get("error_description", [None])[0]

        if state != self.server.expected_state:
            self._respond(400, "Invalid state parameter.")
            self.server.error = OAuthError("Invalid state - possible CSRF")
            self.server.done.set()
            return

        if error:
            message = error_desc or error
            self._respond(400, f"Authorization failed: {message}")
            self.server.error = OAuthError(f"Authorization denied: {message}")
            self.server.done.set()
            return

        if not code:
            self._respond(400, "Missing authorization code.")
            self.server.error = OAuthError("No authorization code in callback")
            self.server.done.set()
            return

        self.server.auth_code = code
        self._respond(200, "Authorization successful. You can close this window.")
        self.server.done.set()

    def _respond(self, status: int, message: str):
        html = f"""<!doctype html>
<html><head><title>inspect-coco</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#111;color:#eee;">
<div style="text-align:center;max-width:36rem;padding:2rem;">
<h1 style="color:{"#7ee787" if status == 200 else "#ff7b72"};">{message}</h1>
{"<script>setTimeout(()=>window.close(),1500)</script>" if status == 200 else ""}
</div></body></html>"""
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # suppress request logs


class _OAuthCallbackServer(HTTPServer):
    """HTTP server that waits for a single OAuth callback."""

    def __init__(self):
        super().__init__((OAUTH_CALLBACK_HOST, 0), _OAuthCallbackHandler)
        self.done = Event()
        self.auth_code: str | None = None
        self.error: OAuthError | None = None
        self.expected_state: str = ""

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def redirect_uri(self) -> str:
        return f"http://{OAUTH_CALLBACK_HOST}:{self.port}/"


def authorize(account: str, role: str | None = None) -> OAuthTokens:
    """Run the full OAuth authorization code flow with PKCE.

    Opens the user's browser to Snowflake's authorize endpoint,
    captures the callback on localhost, exchanges the code for tokens.

    Args:
        account: Snowflake account identifier (e.g., "myorg-myaccount").
        role: Optional Snowflake role to request.

    Returns:
        OAuthTokens with access and refresh tokens.

    Raises:
        OAuthError: If authorization fails or times out.
    """
    account = _normalize_account(account)
    pkce = generate_pkce()
    state = secrets.token_urlsafe(48)

    server = _OAuthCallbackServer()
    server.expected_state = state

    url = _build_authorize_url(account, role, state, pkce, server.redirect_uri)

    # Start callback server in background thread
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        logger.info("Opening browser for Snowflake authentication...")
        webbrowser.open(url)

        # Wait for callback
        if not server.done.wait(timeout=OAUTH_TIMEOUT_SEC):
            raise OAuthError(
                f"OAuth callback timed out after {OAUTH_TIMEOUT_SEC}s. "
                "Did you complete the login in your browser?"
            )

        if server.error:
            raise server.error

        if not server.auth_code:
            raise OAuthError("No authorization code received")

        # Exchange code for tokens
        token_data = exchange_code_for_tokens(account, server.auth_code, pkce, server.redirect_uri)

        tokens = OAuthTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=time.time() + token_data.get("expires_in", 600),
            account=account,
            role=role,
        )

        save_cached_tokens(tokens)
        logger.info("OAuth tokens obtained and cached successfully")
        return tokens

    finally:
        server.shutdown()
        thread.join(timeout=2)


class OAuthError(Exception):
    """Raised when OAuth authorization fails."""
