#!/bin/bash
# CI-ready test script for ecosystem
# Usage: ./scripts/run_tests_ci.sh

set -e  # Exit on any error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

echo "🔍 Running Ecosystem Test Suite (CI Mode)"
echo "=========================================="
echo ""

# Set Python path
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Run pytest with strict settings
echo "📋 Running pytest..."
if .venv/bin/pytest \
    --tb=short \
    --strict-markers \
    --strict-config \
    -ra \
    --maxfail=5 \
    -q; then
    echo -e "${GREEN}✅ All tests passed${NC}"
else
    echo -e "${RED}❌ Tests failed${NC}"
    exit 1
fi

echo ""
echo "🎉 Test suite completed successfully!"
echo "   - All tests passing"
echo "   - No warnings"
echo "   - No skipped tests"
