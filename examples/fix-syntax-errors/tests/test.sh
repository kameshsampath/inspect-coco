#!/bin/bash
set -e

# Verify file runs without syntax errors
python /workspace/broken.py > /tmp/output.txt 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "FAIL: broken.py exited with code $EXIT_CODE"
    cat /tmp/output.txt
    exit 1
fi

# Verify output
if ! grep -q "Result: 42" /tmp/output.txt; then
    echo "FAIL: Output does not contain 'Result: 42'"
    echo "Got:"
    cat /tmp/output.txt
    exit 1
fi

echo "PASS: broken.py runs correctly and outputs 'Result: 42'"
