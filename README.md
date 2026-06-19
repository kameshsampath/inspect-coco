# Inspect CoCo

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
- Docker running
- [Cortex Code CLI](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code)
  installed (beta channel). Verify with: `cortex exec --help`
- `~/.snowflake/connections.toml` with a JWT or PAT connection

## Quickstart

### Install the CoCo plugin

From within Cortex Code, run:

```text
/install-plugin https://github.com/kameshsampath/inspect-coco
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

| Command | What it does |
|---------|-------------|
| `inspect-coco scaffold` | Generate eval suites from plugin structure |
| `inspect-coco run <path>` | Execute eval suite(s) or a single task |
| `inspect-coco idd-check <path>` | Score instruction quality without running evals |

See [docs/cli.md](docs/cli.md) for the full command reference.

## How it works

```mermaid
flowchart TB
    A[instruction.md] --> B{IDD Scoring}
    B -->|pass| C[Docker Sandbox]
    B -->|warn/fail| D[Feedback]
    C --> E[cortex exec]
    E --> F[test.sh]
    F --> G{Score}
    G -->|repeat N epochs| C
    G --> H[pass@k metric]
```

1. **IDD pre-check.** Scores your instruction for
   Goal, Requirements, Constraints, and Output sections.
2. **Sandbox execution.** Runs `cortex exec` inside Docker with your
   Snowflake credentials deployed securely.
3. **Deterministic scoring.** `test.sh` (or pytest) verifies the
   agent output. Exit 0 means pass.
4. **Consistency.** Repeats across epochs for a pass@k reliability
   metric.

## Writing evals

Each eval task is a directory:

```
my-task/
  task.toml         # Configuration: timeout, epochs, IDD threshold
  instruction.md    # Agent prompt (IDD-structured)
  tests/test.sh     # Verification script (exit 0 = pass)
  task.py           # Inspect AI entry point
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

## External references

- [Inspect AI documentation](https://inspect.aisi.org.uk/)
- [Intent-Driven Development: The Shift Developers Can't Ignore](https://blogs.kameshs.dev/intent-driven-development-the-shift-developers-cant-ignore-ef434f94d56c)
- [Intent Compression Ratio: Measuring the Power of Intent](https://blogs.kameshs.dev/intent-compression-ratio-measuring-the-power-of-intent-ceb6faf2e2f9)
- [ICR and Token Economics](https://blogs.kameshs.dev/icr-and-token-economics-9a014a75b399)

## License

Apache-2.0
