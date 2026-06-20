"""OAuth token proxy server (host-process mode).

A lightweight HTTP server that runs as a thread in the inspect-coco
process, serves short-lived access tokens to Docker sandbox containers
via extra_hosts (host-gateway). Reads refresh tokens from the OS keyring,
handles automatic refresh, and triggers browser re-auth if needed.

The proxy binds to 127.0.0.1 on a random available port. The assigned
port is passed to Docker compose via TOKEN_PROXY_PORT env var.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

REFRESH_SKEW_SEC = 120
REAUTH_TIMEOUT_SEC = 30


class TokenState:
    """Thread-safe token state backed by keyring."""

    def __init__(self, account: str, role: str | None = None):
        self._account = account
        self._role = role
        self._access_token: str = ""
        self._expires_at: float = 0.0
        self._lock = threading.Lock()
        self._load_from_keyring()

    def _load_from_keyring(self) -> None:
        """Load current token state from keyring."""
        from inspect_coco.config.oauth import load_cached_tokens

        tokens = load_cached_tokens(account=self._account)
        if tokens:
            self._access_token = tokens.access_token
            self._expires_at = tokens.expires_at

    @property
    def has_tokens(self) -> bool:
        from inspect_coco.config.oauth import load_cached_tokens

        return load_cached_tokens(account=self._account) is not None

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self._expires_at - REFRESH_SKEW_SEC)

    def get_access_token(self) -> dict:
        """Return a valid access token, refreshing if needed."""
        with self._lock:
            if self.is_expired:
                self._refresh()

            expires_in = max(0, int(self._expires_at - time.time()))
            return {
                "access_token": self._access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
            }

    def _refresh(self) -> None:
        """Refresh the access token via keyring-stored refresh_token."""
        from inspect_coco.config.oauth import (
            OAuthError,
            authorize,
            get_valid_token,
            load_cached_tokens,
        )

        tokens = load_cached_tokens(account=self._account)
        if tokens is None:
            raise TokenProxyError("No tokens in keyring for account: " + self._account)

        try:
            refreshed = get_valid_token(tokens)
            self._access_token = refreshed.access_token
            self._expires_at = refreshed.expires_at
            logger.info(
                "Token refreshed for %s (expires_in=%ds)",
                self._account,
                int(self._expires_at - time.time()),
            )
        except OAuthError:
            # Refresh token may be expired — trigger re-auth
            logger.warning("Token refresh failed, attempting browser re-auth...")
            try:
                new_tokens = authorize(
                    account=self._account,
                    role=self._role,
                )
                self._access_token = new_tokens.access_token
                self._expires_at = new_tokens.expires_at
            except OAuthError as exc:
                raise TokenProxyError(f"Re-auth failed: {exc}") from exc


class TokenProxyError(Exception):
    """Raised when the proxy cannot serve a token."""


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler serving token and health endpoints."""

    server: ProxyServer  # type: ignore[assignment]

    def do_GET(self):  # noqa: N802
        if self.path == "/token":
            self._handle_token()
        elif self.path == "/health":
            self._handle_health()
        else:
            self._json_response(404, {"error": "not_found"})

    def _handle_token(self) -> None:
        if not self.server.token_state.has_tokens:
            self._json_response(
                503,
                {
                    "error": "no_tokens",
                    "message": "No OAuth tokens available. Configure authenticator = OAUTH_AUTHORIZATION_CODE.",
                },
            )
            return
        try:
            token_data = self.server.token_state.get_access_token()
            self._json_response(200, token_data)
        except TokenProxyError as exc:
            logger.error("Token proxy error: %s", exc)
            self._json_response(503, {"error": "token_error", "message": str(exc)})

    def _handle_health(self) -> None:
        status = "ok" if self.server.token_state.has_tokens else "standby"
        self._json_response(200, {"status": status})

    def _json_response(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        logger.debug("HTTP %s", format % args)


class ProxyServer(HTTPServer):
    """HTTP server with token state attached."""

    def __init__(self, token_state: TokenState):
        # Bind to 127.0.0.1 on a random available port
        super().__init__(("127.0.0.1", 0), ProxyHandler)
        self.token_state = token_state

    @property
    def port(self) -> int:
        return self.server_address[1]


class TokenProxy:
    """Manages the proxy server lifecycle as a background thread."""

    def __init__(self, account: str, role: str | None = None):
        self._token_state = TokenState(account=account, role=role)
        self._server = ProxyServer(token_state=self._token_state)
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._server.port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        """Start the proxy server in a background daemon thread."""
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="token-proxy",
        )
        self._thread.start()
        logger.info("Token proxy started on port %d", self.port)

    def stop(self) -> None:
        """Gracefully shut down the proxy server."""
        self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Token proxy stopped")

    def __enter__(self) -> TokenProxy:
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()
