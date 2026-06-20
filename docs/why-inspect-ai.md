# Why Inspect AI?

inspect-coco evaluates a coding agent that runs shell commands, modifies
files, and interacts with Snowflake inside a container. This is a
fundamentally different problem from scoring prompt/completion text quality.

This page explains why Inspect AI is the right foundation, how it
compares to alternatives, and what inspect-coco adds on top.

## The problem: evaluating agentic behavior

Most eval frameworks assume a text-in/text-out interaction model: send a
prompt, receive a completion, score the text. Agent evaluation requires:

- Running untrusted code in an isolated environment
- Verifying filesystem state, database state, or process output
- Repeating execution to measure consistency (not just correctness)
- Managing container lifecycles, networking, and credential injection

These requirements eliminate most of the eval landscape immediately.

## What Inspect AI provides

[Inspect AI](https://inspect.aisi.org.uk/) is an open-source framework
from the UK AI Safety Institute (AISI), purpose-built for evaluating
LLM agents in sandboxed environments.

| Capability | What it gives inspect-coco |
|---|---|
| Docker sandbox orchestration | Containers created/destroyed per sample, networking configured automatically |
| Epoch execution + pass@k | Run the same task N times, measure consistency natively |
| Plugin architecture (`@task`, `@agent`, `@scorer`) | Clean extension points without framework forking |
| Structured eval logs | JSON logs with full trajectories, tool calls, scores |
| `inspect view` web UI | Results viewer with no additional infrastructure |
| Multi-sandbox backends | Docker (default), Kubernetes, Proxmox via extension API |
| Model-agnostic agent API | We wrap `cortex exec` as an agent, not a direct LLM call |

The critical differentiator: **sandboxed execution of untrusted agent
code is a first-class primitive**, not a bolt-on. For inspect-coco, where
the agent literally runs `cortex exec` in a container and modifies files,
this is non-negotiable infrastructure.

## Comparison with alternatives

### Promptfoo

YAML-first prompt iteration and red-teaming tool. Fast for comparing
prompt variants side-by-side.

**Why it does not fit:** No sandboxed execution. Assumes text-in/text-out.
Cannot run an agent that modifies a filesystem and verify results with a
shell script. Great for prompt engineering, wrong abstraction for agent
behavioral testing.

### DeepEval

pytest-native evaluation with 50+ built-in metrics (faithfulness,
hallucination, coherence).

**Why it does not fit:** Metrics are text-quality oriented. No concept of
"run code in a container and check the output." Well-suited for RAG
quality, wrong tool for verifying that an agent created the correct file
structure.

### Braintrust

SaaS experiment tracking platform with dataset management and CI
enforcement.

**Why it does not fit:** Commercial platform optimized for LLM-as-judge
scoring at scale. inspect-coco intentionally avoids LLM-as-judge in
favor of deterministic verification. Braintrust's value is in
comparative experiments and production monitoring, not sandboxed agent
execution.

### LangSmith

LangChain-native tracing, evaluation, and production monitoring.

**Why it does not fit:** Tightly coupled to LangChain/LangGraph stack.
No sandbox primitives. Designed for observability of LLM chains, not
behavioral verification of a CLI-based coding agent.

### Eleuther Eval Harness (lm-evaluation-harness)

Standardized academic benchmarks for model-level evaluation (MMLU, ARC,
HellaSwag).

**Why it does not fit:** Designed for model capability benchmarking, not
application-level behavioral testing. Right tool for comparing base
models, wrong tool for testing whether a skill reliably scaffolds a
project.

### Custom solution (no framework)

Build sandbox management, epoch execution, logging, and results viewing
from scratch.

**Why Inspect AI wins:** The sandbox orchestration, structured logging,
and pass@k infrastructure alone represent significant engineering. Inspect
AI is actively maintained, backed by AISI, and has an extension API for
custom sandbox backends. Building this from scratch delays the work that
actually matters: writing evals.

## What inspect-coco adds on top of Inspect AI

Inspect AI provides the execution engine. inspect-coco adds the
domain-specific layer for CoCo skill evaluation:

| Layer | inspect-coco addition |
|---|---|
| IDD pre-scoring | Rule-based quality gate on instruction structure before running expensive Docker evals |
| `cortex exec` agent wrapper | Bridges Inspect AI's agent API to the CoCo CLI |
| Connection resolution | Resolves OAuth/JWT/PAT from `connections.toml` and deploys credentials securely |
| OAuth token proxy | Host-process proxy serves short-lived tokens; refresh token stays in OS keychain, never enters Docker |
| Scaffold from plugins | Reads `.cortex-plugin/plugin.json` and generates eval tasks per leaf skill |
| CoCo plugin integration | Skills (`scaffold`, `create-task`) usable directly inside Cortex Code |
| Deterministic test scripts | `test.sh` as the only scorer, eliminating LLM scoring variance |

## Design principles

1. **Deterministic over probabilistic.** No LLM-as-judge. `test.sh`
   exits 0 or 1. Same result always gets the same grade.

2. **Fail fast on bad instructions.** IDD pre-check catches structural
   problems before burning Docker compute. A vague instruction that would
   fail inconsistently is flagged in seconds.

3. **Consistency over single-pass correctness.** pass@k measures "does
   it work reliably?", not "did it work once?" This directly measures
   what matters for shipping agent skills.

4. **Zero infrastructure beyond Docker.** No SaaS signup, no API keys
   for an eval platform, no hosted services. `pip install` and go.

5. **Security by default.** OAuth refresh tokens stay in the OS keychain.
   Sandbox containers only receive short-lived access tokens. JWT/PAT
   credentials are deployed with minimal privilege.

## When to use something else

- **Prompt A/B comparison:** Promptfoo's side-by-side view is unmatched
  for iterating on prompt wording when the output is text.
- **RAG quality metrics:** DeepEval's faithfulness/relevancy scores are
  purpose-built for retrieval-augmented generation pipelines.
- **LangChain observability:** LangSmith is the obvious choice if your
  stack is LangChain/LangGraph end-to-end.
- **Model benchmarking:** Eleuther harness is the standard for comparing
  base model capabilities on established benchmarks.

inspect-coco is not trying to replace these tools. It solves a specific
problem: does this CoCo skill reliably produce correct output when given
a well-structured instruction?
