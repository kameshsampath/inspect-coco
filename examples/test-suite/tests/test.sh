#!/bin/bash
# Wrapper that runs pytest (for compatibility with default test runner)
set -e
pytest /workspace/tests/test_mathlib.py -v
