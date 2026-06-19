"""Explanatory feedback generator for IDD scores."""

from __future__ import annotations

from inspect_coco.idd.criteria import IDDScore

IDD_TEMPLATE = """  IDD Template:
    [Goal]         — desired outcome / desired state
    [Requirements] — intent statements (not steps)
    [Constraints]  — scope, safety, what not to do
    [Output]       — verifiable success criteria"""

REWRITE_TIP = "  Tip: Use $inspect-coco:create-task for guided IDD-structured task creation."


def explain_score(score: IDDScore, threshold: float = 0.6) -> str:
    """Generate explanatory teaching feedback for an IDD score.

    Produces per-criterion feedback showing what's present, what's missing,
    and concrete suggestions for improvement. Designed to teach users how
    to write better instructions through use.

    Args:
        score: The IDDScore to explain.
        threshold: The passing threshold for display purposes.

    Returns:
        Formatted string with explanatory feedback.
    """
    status = "PASS" if score.total >= threshold else "BELOW THRESHOLD"
    lines = [
        f"[IDD Pre-Check] Score: {score.total:.2f} / 1.0 ({status}, threshold: {threshold})",
        "",
    ]

    # Per-criterion feedback
    for criterion in [score.goal, score.requirements, score.constraints, score.output]:
        mark = "+" if criterion.found else "-"
        lines.append(f"  {mark} {criterion.name}: {criterion.explanation}")
        if not criterion.found:
            lines.append(f"    -> {criterion.suggestion}")

    # Ambiguity warning
    if score.ambiguity_count > 0:
        lines.append("")
        lines.append(
            f"  ! Ambiguity: {score.ambiguity_count} vague word(s) detected "
            f"(specificity: {score.specificity:.2f})"
        )
        lines.append(
            "    -> Replace vague words (appropriate, properly, handle) with concrete terms"
        )

    # Template reminder if below threshold
    if score.total < threshold:
        lines.append("")
        lines.append(IDD_TEMPLATE)
        lines.append("")
        lines.append(REWRITE_TIP)

    return "\n".join(lines)
