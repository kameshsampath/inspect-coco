"""IDD scoring criteria and detection patterns."""

from __future__ import annotations

from dataclasses import dataclass

# Words/phrases that indicate ambiguity (reduce specificity score)
AMBIGUITY_WORDS = [
    "appropriate",
    "properly",
    "correctly",
    "good",
    "nice",
    "adequate",
    "suitable",
    "reasonable",
    "handle",
    "as needed",
    "if necessary",
    "etc",
    "and so on",
    "similar",
]

# Patterns indicating a Goal statement
GOAL_INDICATORS = [
    "goal",
    "objective",
    "desired outcome",
    "desired state",
    "the result should",
    "after completion",
    "the system should",
    "create a",
    "build a",
    "produce a",
    "generate a",
    "ensure that",
]

# Patterns indicating Requirements (intent, not imperative)
REQUIREMENT_INDICATORS = [
    "must",
    "should",
    "shall",
    "requires",
    "requirement",
    "need to",
    "expected to",
    "it is necessary",
]

# Patterns indicating Constraints
CONSTRAINT_INDICATORS = [
    "do not",
    "don't",
    "must not",
    "shall not",
    "avoid",
    "never",
    "only use",
    "restricted to",
    "limited to",
    "constraint",
    "boundary",
    "scope",
    "out of scope",
    "not allowed",
    "forbidden",
]

# Patterns indicating Output/Success criteria
OUTPUT_INDICATORS = [
    "success",
    "output",
    "result",
    "verify",
    "validate",
    "expected",
    "produces",
    "returns",
    "file exists",
    "contains",
    "passes",
    "test",
    "assertion",
    "check that",
    "confirm that",
]


@dataclass(frozen=True)
class CriterionResult:
    """Result for a single IDD criterion."""

    name: str
    score: float  # 0.0 to 1.0
    found: bool  # whether the criterion was detected
    explanation: str  # what was found or what's missing
    suggestion: str  # concrete improvement suggestion


@dataclass(frozen=True)
class IDDScore:
    """Composite IDD score with per-criterion breakdown."""

    total: float  # 0.0 to 1.0 weighted sum
    goal: CriterionResult
    requirements: CriterionResult
    constraints: CriterionResult
    output: CriterionResult
    ambiguity_count: int  # number of ambiguous words found
    specificity: float  # 0.0 to 1.0 (inverse of ambiguity density)
