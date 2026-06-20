# JWT Authentication

Key-pair (JWT) authentication uses an RSA private key to sign tokens locally.

## Configuration

```toml
# ~/.snowflake/connections.toml
[default]
account = "myorg-myaccount"
user = "myuser"
authenticator = "SNOWFLAKE_JWT"
private_key_path = "~/.snowflake/keys/rsa_key.p8"
role = "SYSADMIN"
warehouse = "COMPUTE_WH"
```

## How it works

1. The private key is read from the host filesystem
2. The deployer base64-encodes it and writes it into the sandbox container
3. The container uses the key to sign JWT tokens for each Snowflake API call
4. The key never expires unless manually rotated at the Snowflake level

## Security note

The private key is deployed directly into the sandbox container. This is
acceptable for trusted eval tasks but means compromised sandbox code has
full access to the key. For untrusted evals, consider using
`OAUTH_AUTHORIZATION_CODE` instead.
