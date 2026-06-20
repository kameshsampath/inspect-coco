# Getting Started

This guide walks you through running your first eval with inspect-coco.

## Prerequisites

You need the following tools installed and working before proceeding:

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.12+ | Runtime | [python.org](https://www.python.org/downloads/) |
| Docker | Sandbox execution | [docker.com](https://docs.docker.com/get-started/get-docker/) |
| Snowflake CLI (`snow`) | Connection setup | `pip install snowflake-cli` |
| Cortex Code CLI | Agent runtime | [docs.snowflake.com](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) |

!!! warning "Authentication"

    Password authentication is not supported. You must use one of:

    - **Local OAuth** (`OAUTH_AUTHORIZATION_CODE`) -- recommended for local development. Browser login, tokens stored in OS keychain, no secrets in Docker.
    - **Key-pair authentication (JWT)** with a PEM private key file
    - **Programmatic Access Token (PAT)**

    See the [Security Model](security.md) for a comparison.

## Install inspect-coco

=== "uv (recommended)"

    ```bash
    uv add git+https://github.com/kameshsampath/inspect-coco.git
    ```

=== "pip"

    ```bash
    pip install git+https://github.com/kameshsampath/inspect-coco.git
    ```

## Configure Snowflake connection

inspect-coco reads your existing `~/.snowflake/connections.toml` file. If you already use the `snow` CLI or Cortex Code, you are set.

To create a new connection:

```bash
snow connection add
```

Or edit `~/.snowflake/connections.toml` directly:

=== "OAuth (recommended for local dev)"

    ```toml title="~/.snowflake/connections.toml"
    [default]
    account = "myorg-myaccount"
    user = "myuser"
    authenticator = "OAUTH_AUTHORIZATION_CODE"
    role = "DEVELOPER"
    warehouse = "COMPUTE_WH"
    ```

    No key files or tokens needed. The browser opens automatically on first use.

=== "JWT (key-pair)"

    ```toml title="~/.snowflake/connections.toml"
    [default]
    account = "myorg-myaccount"
    user = "myuser"
    authenticator = "SNOWFLAKE_JWT"
    private_key_file = "~/.snowflake/rsa_key.p8"
    role = "DEVELOPER"
    warehouse = "COMPUTE_WH"
    ```

=== "PAT (programmatic access token)"

    ```toml title="~/.snowflake/connections.toml"
    [default]
    account = "myorg-myaccount"
    user = "myuser"
    authenticator = "PROGRAMMATIC_ACCESS_TOKEN"
    token = "ver:1-hint:..."
    role = "DEVELOPER"
    warehouse = "COMPUTE_WH"
    ```

!!! tip "Non-default connections"

    If your connection is not named `default`, set the environment variable:

    ```bash
    export INSPECT_COCO_SNOWFLAKE_CONNECTION=my-connection
    ```

    Or create a `.env` file in your project root:

    ```dotenv title=".env"
    INSPECT_COCO_SNOWFLAKE_CONNECTION=my-connection
    ```

!!! info "Custom config location"

    Set `SNOWFLAKE_HOME` if your configuration lives somewhere other than `~/.snowflake`.

## Run your first eval

```bash
inspect-coco run examples/hello-world
```

This does the following:

1. Checks instruction quality (IDD score).
2. Starts a Docker container with Cortex Code.
3. Runs the instruction through `cortex exec`.
4. Executes the test script to verify the result.
5. Repeats 3 times (epochs) for consistency measurement.

## View results

```bash
inspect view
```

This opens a browser-based log viewer showing:

- Pass/fail per epoch (pass@k consistency)
- Full conversation transcript (messages, tool calls)
- Token usage and timing
- Scorer output (verification results and IDD quality)

## Next steps

- [Writing Evals](writing-evals.md) for creating your own eval tasks
- [IDD Scoring](idd-scoring.md) for understanding instruction quality
- [Metrics and Reporting](metrics.md) for interpreting results
- [CLI Reference](cli.md) for all available commands
