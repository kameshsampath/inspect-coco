# Architecture

How inspect-coco works internally.

## Overview

inspect-coco runs CoCo (Cortex Code) as an opaque agent inside Docker
containers, then scores the results with deterministic tests.

```
inspect-coco run → IDD pre-check → Docker sandbox → cortex exec → test.sh → Score
```

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Agent | `src/inspect_coco/agents/coco.py` | Runs `cortex exec` in sandbox |
| Credential resolver | `src/inspect_coco/config/connection.py` | Reads ~/.snowflake TOML files |
| Credential deployer | `src/inspect_coco/config/deployer.py` | Mounts keys + config into Docker |
| Trajectory parser | `src/inspect_coco/trajectory/parser.py` | Parses cortex exec JSON output |
| Scorer | `src/inspect_coco/scorers/verification.py` | Runs test command, maps to pass/fail |
| IDD Scorer | `src/inspect_coco/scorers/idd_quality.py` | Reports IDD quality in eval summary |
| IDD scorer | `src/inspect_coco/idd/scorer.py` | Scores instruction quality |
| Task loader | `src/inspect_coco/tasks/loader.py` | Reads task.toml, wires everything |
| Ignore patterns | `src/inspect_coco/ignores.py` | .inspectignore for scaffold |
| Sandbox | `src/inspect_coco/sandbox/` | Dockerfile + compose.yaml |

## How a Run Works

1. **Task loader** reads `task.toml` + `instruction.md`
2. **IDD scorer** checks instruction quality, warns if below threshold
3. **Agent** resolves Snowflake credentials from host TOML files
4. **Deployer** writes `connections.toml` + private key into the Docker container
5. **Agent** writes instruction to a file in the sandbox
6. **Agent** runs `cortex exec --file /tmp/prompt.md --format json --bypass`
7. **Trajectory parser** reads the JSON output (tool calls, response, usage)
8. **Scorer** runs `test.sh` in the sandbox, maps exit code to pass/fail
9. If `epochs > 1`, steps 5-8 repeat and pass@k is computed

## Why Not snowflake-connector-python?

We parse TOML files directly with Python's `tomllib` (stdlib). We don't use `snowflake-connector-python` because:

- We don't connect to Snowflake from the host
- We only need to read config fields and deploy them into Docker
- The cortex CLI inside the container does the actual connecting
- Avoids a ~50MB dependency with native extensions

## Why cortex exec (not cortex --print)?

`cortex exec` is the CI/CD-optimized mode:
- Non-interactive (no TTY needed)
- Plan mode disabled
- Interactive prompts auto-rejected
- `--bypass` allows all tool calls (like `--dangerously-allow-all-tool-calls` but cleaner)
- `--format json` gives structured NDJSON output
- `--file` reads instruction from file (avoids shell escaping)

## Authentication Flow

```
Host: ~/.snowflake/connections.toml
  → resolve_connection() reads TOML
  → deploy_credentials() writes into container:
    → /root/.snowflake/connections.toml (chmod 0600)
    → /root/.snowflake/private_key_*.p8 (chmod 0600, if JWT)
    → /root/.snowflake/cortex/settings.json
```

Supported methods:
- **JWT (key-pair)**: PEM file read, normalized, base64-transported into container
- **PAT**: token written to connections.toml

> [!NOTE]
> Password auth is not supported. JWT and PAT are the recommended secure methods for automation.

## Sandbox

The Docker image (`src/inspect_coco/sandbox/Dockerfile`) includes:
- Python 3.12
- Cortex Code CLI (beta channel by default)
- pytest for test execution
- uv for package management

The `CORTEX_CHANNEL` build arg controls which CLI version is installed (stable/beta/canary).
