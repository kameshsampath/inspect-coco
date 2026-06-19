"""Tests for IDD instruction scorer and explainer."""

from __future__ import annotations

from inspect_coco.idd.explainer import explain_score
from inspect_coco.idd.scorer import score_instruction

# Well-structured IDD instruction (should score high)
GOOD_INSTRUCTION = """\
## Goal

Create a Python function in `/workspace/validator.py` that validates email addresses.

## Requirements

- The function must accept a string and return a boolean
- It should use regex pattern matching for RFC 5322 basic compliance
- It must handle edge cases: empty string, None input, unicode domains

## Constraints

- Do not use any external libraries (stdlib only)
- Do not modify any files outside /workspace/
- Only validate format, not deliverability

## Output

Success criteria:
- File `/workspace/validator.py` exists
- `pytest /workspace/tests/test_validator.py` passes with 0 failures
- Function handles all edge cases without raising exceptions
"""

# Vague, poorly-structured instruction (should score low)
BAD_INSTRUCTION = """\
Make a nice email validator that works properly. Handle edge cases appropriately
and make sure it's good quality code. The output should be reasonable.
"""

# Mixed instruction — has some structure but lacks constraints
MIXED_INSTRUCTION = """\
Create a file called `app.py` that contains a Flask web server.

Requirements:
- Must serve on port 5000
- Should return JSON responses

The app needs to handle errors properly and produce appropriate output.
"""

# ICR Lab examples: same task at different quality levels
# From ~/git/kameshsampath/icr-lab/examples/EXAMPLES.md

VERBOSE_PROMPT = """\
I need to deploy a connector using Snowflake Openflow. First, I need a service
user created in Snowflake. The user should be a service account type. Then I need
a role created for this service user. The role should be granted to the user.
After that, I need network rules configured to allow access to the external
endpoint. The network rule should be wrapped in a network policy. The network
policy needs to be attached to the service user. Then I need an authentication
policy that references the correct role. The auth policy also needs to be attached
to the user. After all of that, I need PAT policy constraints configured, and
then a programmatic access token generated. The PAT should be stored securely.
Finally, validate the token works with NiPyAPI. Please make sure each step is done
in the correct order because the dependencies matter.
"""

INTENT_OPTIMIZED_PROMPT = """\
Deploy Openflow connector: GCS target, PAT auth, NiPyAPI client.
"""

CONTEXT_AWARE_PROMPT = """\
Deploy a Snowflake Openflow connector to GCS. Set up the service user with
appropriate network and auth policies, then generate a PAT for NiPyAPI client
authentication.
"""


class TestScoreInstruction:
    def test_good_instruction_scores_high(self):
        score = score_instruction(GOOD_INSTRUCTION)
        assert score.total >= 0.8, f"Expected >= 0.8, got {score.total}"

    def test_bad_instruction_scores_low(self):
        score = score_instruction(BAD_INSTRUCTION)
        assert score.total <= 0.4, f"Expected <= 0.4, got {score.total}"

    def test_mixed_instruction_scores_middle(self):
        score = score_instruction(MIXED_INSTRUCTION)
        assert 0.3 <= score.total <= 0.8, f"Expected 0.3-0.8, got {score.total}"

    def test_good_has_all_criteria(self):
        score = score_instruction(GOOD_INSTRUCTION)
        assert score.goal.found
        assert score.requirements.found
        assert score.constraints.found
        assert score.output.found

    def test_bad_missing_criteria(self):
        score = score_instruction(BAD_INSTRUCTION)
        assert not score.goal.found
        assert not score.constraints.found

    def test_ambiguity_detected(self):
        score = score_instruction(BAD_INSTRUCTION)
        assert score.ambiguity_count >= 3

    def test_good_low_ambiguity(self):
        score = score_instruction(GOOD_INSTRUCTION)
        assert score.ambiguity_count <= 2  # "handle" in context is acceptable

    def test_empty_instruction(self):
        score = score_instruction("")
        assert score.total <= 0.1

    def test_specificity_inverse_of_ambiguity(self):
        good_score = score_instruction(GOOD_INSTRUCTION)
        bad_score = score_instruction(BAD_INSTRUCTION)
        assert good_score.specificity > bad_score.specificity


class TestICRLabExamples:
    """Test scorer against real ICR Lab prompt examples at varying quality."""

    def test_verbose_prompt_moderate_score(self):
        # Verbose has requirements (must, need) but no explicit structure
        score = score_instruction(VERBOSE_PROMPT)
        assert 0.3 <= score.total <= 0.7, f"Verbose: {score.total}"

    def test_intent_optimized_lower_than_structured(self):
        # Intent-optimized is ultra-concise but lacks IDD sections
        # (Goal/Requirements/Constraints/Output headers missing)
        score = score_instruction(INTENT_OPTIMIZED_PROMPT)
        good_score = score_instruction(GOOD_INSTRUCTION)
        assert score.total < good_score.total

    def test_context_aware_has_ambiguity(self):
        # "appropriate" triggers ambiguity detection
        score = score_instruction(CONTEXT_AWARE_PROMPT)
        assert score.ambiguity_count >= 1

    def test_verbose_scores_higher_than_intent_optimized(self):
        # Verbose has more signal (need, must, validate) even if wordy
        verbose_score = score_instruction(VERBOSE_PROMPT)
        intent_score = score_instruction(INTENT_OPTIMIZED_PROMPT)
        assert verbose_score.total >= intent_score.total

    def test_structured_idd_beats_all_icr_variants(self):
        # Explicitly structured IDD always scores highest
        good = score_instruction(GOOD_INSTRUCTION)
        verbose = score_instruction(VERBOSE_PROMPT)
        intent = score_instruction(INTENT_OPTIMIZED_PROMPT)
        context = score_instruction(CONTEXT_AWARE_PROMPT)
        assert good.total >= verbose.total
        assert good.total >= intent.total
        assert good.total >= context.total


class TestExplainScore:
    def test_below_threshold_shows_template(self):
        score = score_instruction(BAD_INSTRUCTION)
        explanation = explain_score(score, threshold=0.6)
        assert "IDD Template" in explanation
        assert "[Goal]" in explanation
        assert "BELOW THRESHOLD" in explanation

    def test_above_threshold_no_template(self):
        score = score_instruction(GOOD_INSTRUCTION)
        explanation = explain_score(score, threshold=0.6)
        assert "IDD Template" not in explanation
        assert "PASS" in explanation

    def test_shows_suggestions_for_missing(self):
        score = score_instruction(BAD_INSTRUCTION)
        explanation = explain_score(score, threshold=0.6)
        assert "->" in explanation

    def test_shows_ambiguity_warning(self):
        score = score_instruction(BAD_INSTRUCTION)
        explanation = explain_score(score, threshold=0.6)
        assert "Ambiguity" in explanation
        assert "vague word" in explanation

    def test_rewrite_tip(self):
        score = score_instruction(BAD_INSTRUCTION)
        explanation = explain_score(score, threshold=0.6)
        assert "create-task" in explanation
