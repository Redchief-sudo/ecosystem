#!/bin/bash
# Comprehensive cleanup script for ecosystem
# Removes all caches, temporary files, and orphaned data

set -e
echo "🧹 Starting Ecosystem Cleanup..."
echo "=================================="
echo ""

REMOVED_COUNT=0

# 1. Remove Python caches
echo "🗑️  Removing Python caches..."
find . -type d -name "__pycache__" ! -path "./.venv/*" ! -path "./.venv-test/*" -exec rm -rf {} + 2>/dev/null || true
REMOVED_COUNT=$((REMOVED_COUNT + $(find . -type d -name "__pycache__" ! -path "./.venv/*" ! -path "./.venv-test/*" 2>/dev/null | wc -l)))

find . -type f -name "*.pyc" ! -path "./.venv/*" ! -path "./.venv-test/*" -delete 2>/dev/null || true
find . -type f -name "*.pyo" ! -path "./.venv/*" ! -path "./.venv-test/*" -delete 2>/dev/null || true

# 2. Remove pytest caches
echo "🗑️  Removing pytest caches..."
find . -type d -name ".pytest_cache" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

# 3. Remove mypy caches
echo "🗑️  Removing mypy caches..."
find . -type d -name ".mypy_cache" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

# 4. Remove coverage files
echo "🗑️  Removing coverage files..."
find . -type f -name ".coverage" ! -path "./.venv/*" -delete 2>/dev/null || true
rm -rf htmlcov/ .coverage.* 2>/dev/null || true

# 5. Remove log files
echo "🗑️  Removing log files..."
find . -type f -name "*.log" ! -path "./.venv/*" ! -path "./logs/*" -delete 2>/dev/null || true

# 6. Remove temporary files
echo "🗑️  Removing temporary files..."
find . -type f -name "*.tmp" ! -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*.swp" ! -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*.swo" ! -path "./.venv/*" -delete 2>/dev/null || true
find . -type f -name "*~" ! -path "./.venv/*" -delete 2>/dev/null || true

# 7. Remove build artifacts
echo "🗑️  Removing build artifacts..."
find . -type d -name "build" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "dist" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

# 8. Remove node_modules if any exist
echo "🗑️  Removing node_modules..."
find . -type d -name "node_modules" ! -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

# 9. Remove DS_Store files (macOS)
echo "🗑️  Removing .DS_Store files..."
find . -name ".DS_Store" -delete 2>/dev/null || true

# 10. Remove empty directories
echo "🗑️  Removing empty directories..."
find . -type d -empty ! -path "./.venv/*" ! -path "./.git/*" -delete 2>/dev/null || true

# 11. Clean up test outputs
echo "🗑️  Removing test outputs..."
rm -rf test-output/ test-results/ .hypothesis/ 2>/dev/null || true

# 12. Remove lockfiles
echo "🗑️  Removing lockfiles..."
find . -type f -name "*.lock" ! -path "./.venv/*" ! -path "./.git/*" -delete 2>/dev/null || true

echo ""
echo "✅ Cleanup Complete!"
echo ""

# Verify cleanup
echo "📊 Remaining items check:"
PYCACHE_COUNT=$(find . -type d -name "__pycache__" ! -path "./.venv/*" ! -path "./.venv-test/*" 2>/dev/null | wc -l)
PYTEST_COUNT=$(find . -type d -name ".pytest_cache" ! -path "./.venv/*" 2>/dev/null | wc -l)
PYC_COUNT=$(find . -type f -name "*.pyc" ! -path "./.venv/*" ! -path "./.venv-test/*" 2>/dev/null | wc -l)
LOG_COUNT=$(find . -type f -name "*.log" ! -path "./.venv/*" ! -path "./logs/*" 2>/dev/null | wc -l)

echo "   __pycache__ directories: $PYCACHE_COUNT"
echo "   .pytest_cache directories: $PYTEST_COUNT"
echo "   .pyc files: $PYC_COUNT"
echo "   .log files: $LOG_COUNT"

if [ $PYCACHE_COUNT -eq 0 ] && [ $PYTEST_COUNT -eq 0 ] && [ $PYC_COUNT -eq 0 ] && [ $LOG_COUNT -eq 0 ]; then
    echo ""
    echo "✅ Working directory is CLEAN and ready for fingerprinting"
    exit 0
else
    echo ""
    echo "⚠️  Some items remain (may be in virtual environments)"
    exit 0
fi
