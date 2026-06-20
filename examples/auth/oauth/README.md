# OAuth Authentication (Local OAuth Token Proxy)

OAuth Authorization Code with PKCE provides the strongest security posture for
eval sandboxes. The sandbox container never receives any long-lived credential.

## Configuration

```toml
# ~/.snowflake/connections.toml
[default]
account = "myorg-myaccount"
user = "myuser"
authenticator = "OAUTH_AUTHORIZATION_CODE"
role = "SYSADMIN"
warehouse = "COMPUTE_WH"
```

## How it works

1. On first use, inspect-coco opens your browser to complete the Snowflake
   OAuth login (Authorization Code + PKCE flow)
2. Tokens are cached at `~/.snowflake/inspect-coco-oauth.json`
3. When an eval starts, the compose stack launches a hardened **token proxy
   sidecar** alongside the sandbox
4. The proxy reads the refresh token via a Docker secret (tmpfs, never on disk
   in the container)
5. The sandbox fetches short-lived access tokens (~10 min) from the proxy via
   `GET http://token-proxy:8765/token`
6. The sandbox never holds any long-lived secret

## Security properties

- Refresh token is only in the proxy sidecar (hardened: read-only fs, no shell,
  no capabilities)
- Sandbox only gets tokens that expire in ~10 minutes
- If sandbox is compromised, attacker window is limited to token TTL
- Compose stack tears down after eval, all secrets vanish from tmpfs

## First-time setup

No manual setup needed. The browser flow triggers automatically on first
connection resolution. Ensure the `SNOWFLAKE$LOCAL_APPLICATION` OAuth
integration is enabled on your Snowflake account.
