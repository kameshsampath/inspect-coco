# Architecture

This page describes how inspect-coco works internally and how the pieces fit together.

## Execution flow

When you run `inspect-coco run`, the following sequence occurs:

```mermaid
sequenceDiagram
    participant CLI as inspect-coco run
    participant Loader as Task Loader
    participant IDD as IDD Scorer
    participant Docker as Docker Sandbox
    participant Agent as cortex exec
    participant Test as Verification

    CLI->>Loader: Read task.toml + instruction.md
    Loader->>IDD: Score instruction quality
    IDD-->>Loader: IDD score + metadata
    Loader->>Docker: Start container, mount files
    loop For each epoch (pass@k)
        Docker->>Agent: Run cortex exec with instruction
        Agent-->>Docker: Agent output (files, changes)
        Docker->>Test: Execute test.sh
        Test-->>Docker: Exit code (0=pass, 1=fail)
    end
    Docker-->>CLI: Eval log with scores
```

## Credential flow

The agent needs Snowflake credentials to call the Cortex API. The credential flow varies by authentication method:

```mermaid
flowchart TD
    A["~/.snowflake/connections.toml"] --> B[resolve_connection]
    B --> C{authenticator?}
    C -->|OAUTH_AUTHORIZATION_CODE| D[Load from OS keychain]
    C -->|SNOWFLAKE_JWT| E[Read PEM key file]
    C -->|PROGRAMMATIC_ACCESS_TOKEN| F[Read token]

    D --> G{Tokens cached?}
    G -->|Yes| H[Start token proxy thread]
    G -->|No| I[Browser OAuth flow]
    I --> J[Store in keychain]
    J --> H

    E --> K[deploy_credentials]
    F --> K
    H --> L["Sandbox calls GET /token via host-gateway"]

    K --> M["/root/.snowflake/connections.toml (inside container)"]
    L --> M
    M --> N[cortex exec uses connection]
```

| Auth method | Secret storage | What enters Docker | Refresh capability |
|-------------|---------------|-------------------|-------------------|
| OAuth (recommended) | OS keychain (encrypted) | Short-lived access token only | Automatic (silent + browser re-auth) |
| JWT | Host filesystem | PEM private key | N/A (key never expires) |
| PAT | Host filesystem / env var | Token value | N/A (long-lived) |

!!! tip "Recommended for local development"

    Use `authenticator = "OAUTH_AUTHORIZATION_CODE"` for the strongest security posture. The sandbox never holds any long-lived credential. See the [Security Model](security.md) page for details.

!!! note "Connection resolution"

    The resolver checks `INSPECT_COCO_SNOWFLAKE_CONNECTION` first, then falls back to a connection named `default` in your TOML file. Run `snow connection list` to see available connections.

## Sandbox environment

Each eval runs inside an isolated Docker container built from `src/inspect_coco/sandbox/Dockerfile`:

```mermaid
flowchart LR
    subgraph Container
        direction TB
        CoCo[Cortex Code CLI]
        Py[Python 3.12]
        Pytest[pytest]
        UV[uv]
    end

    subgraph HostAccess ["Host Access (via extra_hosts)"]
        direction TB
        TokenProxy["Token Proxy (OAuth)"]
    end

    subgraph Mounted
        direction TB
        Creds[Snowflake credentials]
        Starter[starter/ files]
        Tests[tests/ scripts]
    end

    Mounted --> Container
    HostAccess --> Container
    Container --> Result[Exit code + stdout]
```

The container includes:

- **Python 3.12** as the base runtime
- **Cortex Code CLI** (beta channel by default, controlled via `CORTEX_CHANNEL` build arg)
- **pytest** for running test suites
- **uv** for package management inside the sandbox
- **host-gateway access** to the token proxy (OAuth connections only)

## Scoring pipeline

Two scorers run after the agent completes:

```mermaid
flowchart TD
    A[Agent completes] --> B[verification scorer]
    A --> C[idd_quality scorer]
    B --> D["Runs test.sh in sandbox"]
    D --> E["Score: 1.0 (pass) or 0.0 (fail)"]
    C --> F["Scores instruction text"]
    F --> G["Score: 0.0 to 1.0"]
    E --> H[Eval log]
    G --> H
```

The **verification** scorer produces `passed` and `total` metrics (how many epochs passed out of how many ran). The **idd_quality** scorer produces an `idd_score` metric (instruction quality rating).

## Configuration merge order

When multiple configuration sources exist, they merge with this priority:

```mermaid
flowchart BT
    A[Built-in defaults] --> B[suite.yaml defaults]
    B --> C[suite.yaml per-task overrides]
    C --> D[task.toml values]
    D --> E[CLI flags]
    E --> F[Final resolved config]
```

The highest priority source wins for each setting. CLI flags always override everything else.
