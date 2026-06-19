# Scorers

Scorers run after the agent completes and produce `Score` objects with metrics.

## Verification

Runs test commands in the sandbox and reports pass/fail.

::: inspect_coco.scorers.verification
    options:
      members:
        - verification
        - passed
        - total

## IDD Quality

Reports instruction quality as a score in the eval summary.

::: inspect_coco.scorers.idd_quality
    options:
      members:
        - idd_quality
        - idd_score
