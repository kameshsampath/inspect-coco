# COCO.md - Project Conventions

## Package Management
- Use `uv` for all dependency management
- `uv sync` to install, `uv run` to execute

## Code Quality
- `ruff` for linting and formatting (line-length 100)
- `pyright` for type checking (standard mode)
- Pre-commit hooks enforce both on every commit

## Commits
- Conventional Commits required (enforced by pre-commit)
- Logical commits: one concern per commit
- Prefixes: feat, fix, chore, docs, refactor, test

## Design Principles
- IDD: express tasks as intent (Goal/Requirements/Constraints/Output)
- Atomic evals: one eval = one skill instruction
- No password auth (JWT + PAT only)

## Running Tests
```bash
uv run pytest
uv run ruff check src/ tests/
uv run pyright
```
