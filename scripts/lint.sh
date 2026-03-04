#!/bin/bash
# Run linting and formatting checks

set -e  # Exit on error

echo "Running code quality checks..."

echo ""
echo "1. Checking code formatting with black..."
black --check execution/ services/ tests/ || {
    echo "Code formatting issues found. Run 'black .' to fix."
    exit 1
}

echo ""
echo "2. Running flake8..."
flake8 execution/ services/ tests/

echo ""
echo "3. Running mypy type checking..."
mypy execution/ services/

echo ""
echo "All checks passed!"
