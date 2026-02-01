#!/bin/bash
# Quick script to check GitHub Actions workflow status

echo "=== GITHUB ACTIONS WORKFLOW STATUS ==="
echo ""
echo "Repository: Redchief-sudo/ecosystem"
echo "Branch: main"
echo "Latest Commit: $(git log --oneline -1)"
echo ""
echo "To view workflow runs:"
echo "  https://github.com/Redchief-sudo/ecosystem/actions"
echo ""
echo "Expected workflow: 'Ecosystem CI/CD Pipeline'"
echo "Expected jobs: test, lint, security"
echo ""
echo "If using GitHub CLI:"
echo "  gh run list --limit 5"
echo "  gh run view <run-id>"
echo ""
