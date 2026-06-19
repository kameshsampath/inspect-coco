#!/bin/bash
set -e

# Verify file exists
if [ ! -f /workspace/env-check.txt ]; then
    echo "FAIL: /workspace/env-check.txt does not exist"
    exit 1
fi

# Verify content matches expected env var value
CONTENT=$(cat /workspace/env-check.txt)
EXPECTED="from-compose"

if [ "$CONTENT" != "$EXPECTED" ]; then
    echo "FAIL: Content mismatch"
    echo "  Expected: '$EXPECTED'"
    echo "  Got:      '$CONTENT'"
    exit 1
fi

echo "PASS: env-check.txt contains correct CUSTOM_ENV value"
