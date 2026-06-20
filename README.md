# Inspect CoCo

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://kameshsampath.github.io/inspect-coco/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Sandbox Image](https://img.shields.io/badge/ghcr.io-inspect--coco--sandbox-purple?logo=docker)](https://ghcr.io/kameshsampath/inspect-coco-sandbox)

> [!NOTE]
> Early development. The API may change. Not yet published to PyPI.

Deterministic evaluations for
[Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code)
(CoCo) skills using [Inspect AI](https://inspect.aisi.org.uk/).

- Scaffold eval suites from existing CoCo plugins in one command.
- Score instruction quality with IDD (Intent-Driven Development) analysis.
- Measure consistency via pass@k (repeated runs with epochs).

## Prerequisites

- Python 3.12+
- Docker 20.10+ running
- [Cortex Code CLI](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code)
  installed (beta channel). Verify with: `cortex exec --help`
- `~/.snowflake/connections.toml` with a supported authenticator:

| Authenticator | Best for | Notes |
|--------------|----------|-------|
| `OAUTH_AUTHORIZATION_CODE` | Local dev (recommended) | Browser login, keychain storage, no secrets in Docker |
| `SNOWFLAKE_JWT` | CI / automation | Key-pair auth, key deployed into sandbox |
| `PROGRAMMATIC_ACCESS_TOKEN` | CI / automation | Long-lived token deployed into sandbox |

See [Security Model](docs/security.md) for details on how credentials are handled.

## Quickstart

### Install the CoCo plugin

From within Cortex Code, run:

```text
cortex plugin https://github.com/kameshsampath/inspect-coco
```

This registers the `inspect-coco` skills (`scaffold` and `create-task`)
in your project.

### Configure

```bash
cp .env.example .env
# Set INSPECT_COCO_SNOWFLAKE_CONNECTION to your connection.
# Run: grep "^\[" ~/.snowflake/connections.toml to see available options.
```

### Run your first eval

```bash
# Check instruction quality (no Docker needed)
inspect-coco idd-check examples/

# Run an eval (requires Docker and a Snowflake connection)
inspect-coco run examples/hello-world

# View results in the browser
inspect view
```

## Usage

### As a CoCo plugin (recommended)

Once the plugin is installed, invoke skills directly from Cortex Code.
This gives you interactive guidance, IDD template generation, and
context-aware scaffolding.

| Skill | What it does |
|-------|-------------|
| `$inspect-coco:scaffold` | Scan plugin structure, generate eval suites per leaf skill |
| `$inspect-coco:create-task` | Guided single-task creation with IDD structure |

### As a CLI

The CLI provides the same functionality for scripts, CI pipelines,
and terminal workflows.

#### Install and use

```shell
# Install the package
uv add git+https://github.com/kameshsampath/inspect-coco.git

# Verify the CLI is available
inspect-coco --help
```

| Command | What it does |
|---------|-------------|
| `inspect-coco scaffold` | Generate eval suites from plugin structure |
| `inspect-coco run <path>` | Execute eval suite(s) or a single task |
| `inspect-coco idd-check <path>` | Score instruction quality without running evals |

See [docs/cli.md](docs/cli.md) for the full command reference.

## How it works

```mermaid
sequenceDiagram
    participant User as inspect-coco run
    participant IDD as IDD Scorer
    participant Auth as Connection Resolver
    participant Proxy as Token Proxy
    participant Docker as Docker Sandbox
    participant Agent as cortex exec

    User->>IDD: Score instruction.md
    IDD-->>User: IDD quality gate

    User->>Auth: resolve_connection()
    alt OAuth
        Auth->>Auth: Load from keyring / browser login
        Auth->>Proxy: Start proxy thread (random port)
    else JWT / PAT
        Auth->>Auth: Load key or token from config
    end

    User->>Docker: Start sandbox container
    loop For each epoch
        Docker->>Agent: Run cortex exec
        alt OAuth
            Agent->>Proxy: GET /token (via host-gateway)
            Proxy-->>Agent: Short-lived access_token
        end
        Agent-->>Docker: Agent output
        Docker->>Docker: Run test.sh
    end
    Docker-->>User: Eval log with pass@k score
```

Agents are non-deterministic. The same vague prompt produces different
outputs on every run. IDD structure narrows what the agent can
reasonably do, which directly improves pass@k consistency:

1. **IDD pre-check** gates execution. A clear Goal fixes the target,
   Constraints close divergent paths, and concrete Output criteria make
   scoring binary. Vague instructions get flagged before they waste
   compute.
2. **Sandbox execution** runs `cortex exec` inside Docker with your
   Snowflake credentials deployed securely. Same environment every time.
3. **Deterministic scoring** via `test.sh` (or pytest) checks facts,
   not style. Exit 0 means pass.
4. **Epochs** repeat the run N times. A well-structured IDD instruction
   passes consistently; a vague one does not.

## Viewing results

Eval results are saved as `.eval` files in the `logs/` directory.

```shell
# Open the web viewer (serves all logs)
inspect view

# List recent eval logs
inspect log list

# Dump a specific log as JSON
inspect log dump logs/<log-file>.eval
```

## Writing evals

Each eval task is a directory:

```
my-task/
  task.toml         # Configuration: timeout, epochs, IDD threshold
  instruction.md    # Agent prompt (IDD-structured)
  tests/test.sh     # Verification script (exit 0 = pass)
```

The `instruction.md` follows the IDD template:

```markdown
## Goal
<desired outcome>

## Requirements
<intent statements, not steps>

## Constraints
<scope, safety, what not to do>

## Output
<verifiable success criteria>
```

Group tasks into suites with `suite.yaml` for shared defaults.
See [docs/writing-evals.md](docs/writing-evals.md) for details.

## Scaffold from existing skills

If you already have a CoCo plugin with skills:

```text
# From within Cortex Code (recommended)
$inspect-coco:scaffold
```

```bash
# Or via CLI
inspect-coco scaffold --dry-run   # preview what would be generated
inspect-coco scaffold             # generate the files
```

This reads `.cortex-plugin/plugin.json`, detects leaf skills (skips routers),
and generates IDD-structured eval tasks for each skill.

## Build locally

```bash
# Clone the repository
git clone https://github.com/kameshsampath/inspect-coco.git
cd inspect-coco

# Install with uv (editable mode)
uv sync

# Run tests
uv run pytest tests/ --ignore=tests/integration

# Use the CLI
uv run inspect-coco --help
```

Or install as a dependency in another project:

```bash
uv add git+https://github.com/kameshsampath/inspect-coco.git
```

## Project structure

```
src/inspect_coco/
  cmd/              # CLI commands (run, idd-check, scaffold)
  agents/           # CoCo agent (cortex exec wrapper)
  config/           # Connection resolution and credential deployment
  idd/              # IDD scoring and explainer
  scaffold.py       # Eval suite generation from plugin structure
  suite.py          # suite.yaml loader
  tasks/            # Task loader (task.toml + instruction.md)
  scorers/          # Deterministic test-based scoring
  trajectory/       # cortex exec output parser
  sandbox/          # Dockerfile and default compose.yaml
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli.md)
- [Task Configuration](docs/task-toml.md)
- [Suite Configuration](docs/suite-yaml.md)
- [IDD Scoring](docs/idd-scoring.md)
- [Writing Evals](docs/writing-evals.md)
- [Architecture](docs/architecture.md)
- [Security Model](docs/security.md)

## External references

- [Inspect AI documentation](https://inspect.aisi.org.uk/)
- [Intent-Driven Development: The Shift Developers Can't Ignore](https://blogs.kameshs.dev/intent-driven-development-the-shift-developers-cant-ignore-ef434f94d56c)
- [Intent Compression Ratio: Measuring the Power of Intent](https://blogs.kameshs.dev/intent-compression-ratio-measuring-the-power-of-intent-ceb6faf2e2f9)
- [ICR and Token Economics](https://blogs.kameshs.dev/icr-and-token-economics-9a014a75b399)

## License

Apache-2.0. See [LICENSE](LICENSE) for details.

## Citation

If you use inspect-coco in your research or publications:

```bibtex
@software{inspect_coco,
  author = {Sampath, Kamesh},
  title = {inspect-coco: Deterministic Evaluations for Cortex Code Skills},
  url = {https://github.com/kameshsampath/inspect-coco},
  license = {Apache-2.0}
}
```
