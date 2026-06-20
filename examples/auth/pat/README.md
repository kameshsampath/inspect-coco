# PAT Authentication

Programmatic Access Token (PAT) authentication uses a long-lived token issued by Snowflake.

## Configuration

```toml
# ~/.snowflake/connections.toml
[default]
account = "myorg-myaccount"
user = "myuser"
authenticator = "PROGRAMMATIC_ACCESS_TOKEN"
token = "ver:1-hint:1234567890abcdef..."
role = "SYSADMIN"
warehouse = "COMPUTE_WH"
```

## How it works

1. The PAT is read from the host's connections.toml
2. The deployer writes it into the sandbox container's connections.toml
3. The container uses the token directly for Snowflake API calls
4. PATs are long-lived (configurable expiry at the Snowflake level)

## Security note

The PAT is deployed directly into the sandbox container as a token value.
This is simpler than JWT (no key management) but carries the same risk:
compromised sandbox code has access to the full token. For untrusted evals,
consider using `OAUTH_AUTHORIZATION_CODE` instead.
