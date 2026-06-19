"""Heuristic IDD instruction scorer."""

from __future__ import annotations

import re

from inspect_coco.idd.criteria import (
    AMBIGUITY_WORDS,
    CONSTRAINT_INDICATORS,
    GOAL_INDICATORS,
    OUTPUT_INDICATORS,
    REQUIREMENT_INDICATORS,
    CriterionResult,
    IDDScore,
)


def score_instruction(text: str) -> IDDScore:
    """Score an instruction.md against IDD criteria.

    Performs heuristic analysis (no LLM call) checking for the presence
    of Goal, Requirements, Constraints, and Output/Success criteria.

    Args:
        text: The instruction markdown content.

    Returns:
        IDDScore with 0.0-1.0 total and per-criterion breakdown.
    """
    text_lower = text.lower()
    lines = text.splitlines()

    # Score each criterion
    goal = _score_goal(text_lower, lines)
    requirements = _score_requirements(text_lower, lines)
    constraints = _score_constraints(text_lower, lines)
    output = _score_output(text_lower, lines)

    # Measure ambiguity
    ambiguity_count = _count_ambiguity(text_lower)
    word_count = len(text.split())
    ambiguity_density = ambiguity_count / max(word_count, 1)
    specificity = max(0.0, 1.0 - (ambiguity_density * 20))  # penalize heavily

    # Weighted total (equal weights)
    total = (goal.score + requirements.score + constraints.score + output.score) / 4.0

    return IDDScore(
        total=round(total, 2),
        goal=goal,
        requirements=requirements,
        constraints=constraints,
        output=output,
        ambiguity_count=ambiguity_count,
        specificity=round(specificity, 2),
    )


def _score_goal(text_lower: str, lines: list[str]) -> CriterionResult:
    """Check for clear goal/desired outcome."""
    # Check for explicit section header
    has_header = _has_section_header(
        lines, ["goal", "objective", "desired outcome", "desired state"]
    )

    # Check for goal indicator phrases
    matches = [ind for ind in GOAL_INDICATORS if ind in text_lower]

    if has_header:
        score = 1.0
        explanation = "Goal section found with clear desired outcome."
    elif len(matches) >= 2:
        score = 0.8
        explanation = f"Goal indicators found: {', '.join(matches[:3])}"
    elif len(matches) == 1:
        score = 0.5
        explanation = f"Weak goal signal: '{matches[0]}'. Consider adding an explicit Goal section."
    else:
        score = 0.0
        explanation = "No clear goal or desired outcome statement found."

    return CriterionResult(
        name="Goal",
        score=score,
        found=score > 0,
        explanation=explanation,
        suggestion='Add: "[Goal] Create/produce/ensure <specific desired state>"',
    )


def _score_requirements(text_lower: str, lines: list[str]) -> CriterionResult:
    """Check for intent-based requirements (not imperative steps)."""
    has_header = _has_section_header(lines, ["requirements", "requirement", "needs"])

    matches = [ind for ind in REQUIREMENT_INDICATORS if ind in text_lower]

    if has_header and len(matches) >= 2:
        score = 1.0
        explanation = "Requirements section with intent statements found."
    elif len(matches) >= 3:
        score = 0.8
        explanation = f"Multiple requirement indicators: {', '.join(matches[:3])}"
    elif len(matches) >= 1:
        score = 0.5
        explanation = f"Some requirements found: {', '.join(matches[:2])}"
    else:
        score = 0.2  # most instructions have implicit requirements
        explanation = "No explicit requirements stated. Instructions may be too imperative."

    return CriterionResult(
        name="Requirements",
        score=score,
        found=score > 0.3,
        explanation=explanation,
        suggestion='Add: "[Requirements] The system must/should <intent statement>"',
    )


def _score_constraints(text_lower: str, lines: list[str]) -> CriterionResult:
    """Check for constraints/boundaries."""
    has_header = _has_section_header(lines, ["constraints", "constraint", "boundaries", "scope"])

    matches = [ind for ind in CONSTRAINT_INDICATORS if ind in text_lower]

    if has_header:
        score = 1.0
        explanation = "Constraints section defines clear boundaries."
    elif len(matches) >= 3:
        score = 0.8
        explanation = f"Multiple constraints found: {', '.join(matches[:3])}"
    elif len(matches) >= 1:
        score = 0.5
        explanation = (
            f"Some constraints: {', '.join(matches[:2])}. Consider adding more boundaries."
        )
    else:
        score = 0.0
        explanation = "No constraints defined. Agent may take unexpected paths."

    return CriterionResult(
        name="Constraints",
        score=score,
        found=score > 0,
        explanation=explanation,
        suggestion='Add: "[Constraints] Do not modify X / Only use Y / Scope limited to Z"',
    )


def _score_output(text_lower: str, lines: list[str]) -> CriterionResult:
    """Check for verifiable output/success criteria."""
    has_header = _has_section_header(lines, ["output", "success", "verification", "expected"])

    matches = [ind for ind in OUTPUT_INDICATORS if ind in text_lower]

    # Check for specific verifiable patterns (file paths, concrete values)
    has_specific = bool(re.search(r'["\'`/]\S+\.\w+', text_lower))  # file paths/names

    if has_header and (len(matches) >= 2 or has_specific):
        score = 1.0
        explanation = "Clear output/success criteria with verifiable conditions."
    elif len(matches) >= 3 or (len(matches) >= 1 and has_specific):
        score = 0.8
        explanation = f"Output indicators found: {', '.join(matches[:3])}"
    elif len(matches) >= 1:
        score = 0.5
        explanation = f"Weak success criteria: {', '.join(matches[:2])}"
    else:
        score = 0.0
        explanation = "No success criteria defined. How will we know it worked?"

    return CriterionResult(
        name="Output",
        score=score,
        found=score > 0,
        explanation=explanation,
        suggestion='Add: "[Output] Success: <file> exists / <test> passes / <condition> is true"',
    )


def _has_section_header(lines: list[str], keywords: list[str]) -> bool:
    """Check if any line is a markdown header containing one of the keywords."""
    for line in lines:
        line_lower = line.lower().strip()
        if line_lower.startswith("#") or line_lower.startswith("**"):
            for kw in keywords:
                if kw in line_lower:
                    return True
    return False


def _count_ambiguity(text_lower: str) -> int:
    """Count ambiguous words/phrases in the text."""
    count = 0
    for word in AMBIGUITY_WORDS:
        count += text_lower.count(word)
    return count
