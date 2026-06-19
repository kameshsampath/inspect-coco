#!/bin/bash
# This test will likely fail because the instruction is too vague
# to produce consistent, testable output.
set -e

test -f /workspace/calculator.py
python /workspace/calculator.py
