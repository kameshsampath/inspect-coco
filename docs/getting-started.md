# Getting Started

This guide walks you through running your first eval with inspect-coco.

## What You Need

- Python 3.12+
- Docker (running)
- A Snowflake account with either:
  - Key-pair authentication (JWT), or
  - A Programmatic Access Token (PAT)
- Cortex Code CLI (beta channel) installed

> [!NOTE]
> Password authentication is not supported. Use key-pair (JWT) or PAT.

## Install

```bash
uv add git+https://github.com/kameshsampath/inspect-coco.git
```

Or with pip:

```bash
pip install git+https://github.com/kameshsampath/inspect-coco.git
```

## Configure Snowflake Connection

inspect-coco reads your existing `~/.snowflake/connections.toml` file.
If you already use `snow` CLI or Cortex Code, you're set.

Example `~/.snowflake/connections.toml`:

```toml
[default]
account = "myorg-myaccount"
user = "myuser"
authenticator = "SNOWFLAKE_JWT"
private_key_file = "~/.snowflake/rsa_key.p8"
role = "DEVELOPER"
warehouse = "COMPUTE_WH"
```

> [!TIP]
> Set `SNOWFLAKE_HOME` if your config lives somewhere other than `~/.snowflake`.

## Run Your First Eval

```bash
inspect eval examples/hello-world/task.py
```

This will:
1. Check the instruction quality (IDD score)
2. Start a Docker container with Cortex Code
3. Run the instruction through `cortex exec`
4. Execute the test script to verify the result
5. Repeat 3 times (epochs) for consistency measurement

## What You'll See

```
[IDD Pre-Check] Score: 1.00 / 1.0 (PASS, threshold: 0.6)

Task: hello-world
  Epochs: 3
  Pass rate: 3/3 (100%)
```

## Next Steps

- [Task Configuration](task-toml.md) - how to configure eval tasks
- [IDD Scoring](idd-scoring.md) - how instruction quality is measured
- [Writing Evals](writing-evals.md) - create your own eval tasks
