#!/bin/bash
set -e

# Verify file exists
if [ ! -f /workspace/hello.txt ]; then
    echo "FAIL: /workspace/hello.txt does not exist"
    exit 1
fi

# Verify content
CONTENT=$(cat /workspace/hello.txt)
EXPECTED="Hello, World!"

if [ "$CONTENT" != "$EXPECTED" ]; then
    echo "FAIL: Content mismatch"
    echo "  Expected: '$EXPECTED'"
    echo "  Got:      '$CONTENT'"
    exit 1
fi

echo "PASS: /workspace/hello.txt exists with correct content"
