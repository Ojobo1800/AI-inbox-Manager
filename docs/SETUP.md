# Setup Guide

Complete setup instructions for new developers.

## Prerequisites

- Python 3.9 or higher
- Git
- Text editor or IDE (VS Code recommended)

## Initial Setup

### 1. Clone Repository

```bash
# If using git
git clone <repository-url>
cd <project-directory>
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

# Verify activation (should show path to venv)
which python  # Mac/Linux
where python  # Windows
```

### 3. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Or install in development mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
pytest --version
python -c "import execution"
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Use a text editor to add required values
```

Example `.env` file:
```
ENVIRONMENT=dev
LOG_LEVEL=DEBUG
API_BASE_URL=https://api-dev.example.com
```

### 5. Verify Setup

```bash
# Run tests to verify everything works
pytest

# Should see output like:
# ===== test session starts =====
# collected X items
# tests/... PASSED
# ===== X passed in Y.YYs =====
```

## Development Environment

### Recommended VS Code Extensions

- Python (Microsoft)
- Pylance
- Python Test Explorer
- GitLens
- Better Comments

### VS Code Settings

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

## Project Structure Overview

```
project/
│
├── agents/          # Agent definitions (no code)
├── directives/      # SOPs in plain language
├── execution/       # Your code goes here
├── services/        # Workers and scheduled jobs
├── config/          # Environment configs
├── tests/           # All tests
├── docs/            # Documentation
└── tmp/             # Scratch space (gitignored)
```

## Running Tests

### Basic Test Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific file
pytest tests/execution/test_example_script.py

# Run specific test
pytest tests/execution/test_example_script.py::TestProcessData::test_process_valid_records

# Run with verbose output
pytest -v

# Run and show print statements
pytest -s
```

### Integration Tests

Integration tests require opt-in:

```bash
# Set environment variable
export TEST_INTEGRATION=1  # Mac/Linux
set TEST_INTEGRATION=1     # Windows

# Or run inline
TEST_INTEGRATION=1 pytest tests/integration/
```

## Running Scripts

### Example Script

```bash
# Create test input
mkdir -p tmp
echo '[{"id": "1", "value": 10}]' > tmp/input.json

# Run script
python execution/example_script.py tmp/input.json tmp/output.json

# Check output
cat tmp/output.json
```

### Adding Your Own Script

1. Create script in `execution/`
2. Follow the pattern in `example_script.py`
3. Separate business logic from I/O
4. Make core functions testable

```python
# execution/my_script.py

def my_business_logic(data):
    """Pure, testable function."""
    return processed_data

def main():
    """CLI wrapper - handles I/O."""
    data = load_data()
    result = my_business_logic(data)
    save_result(result)

if __name__ == "__main__":
    main()
```

5. Write tests in `tests/execution/test_my_script.py`

## Common Issues

### Issue: "pytest: command not found"

**Solution**: Make sure virtual environment is activated and pytest is installed.

```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install pytest
```

### Issue: "ModuleNotFoundError: No module named 'execution'"

**Solution**: Install the package in development mode.

```bash
pip install -e .
```

### Issue: Tests fail with import errors

**Solution**: Ensure `__init__.py` files exist in all directories.

```bash
# These should all exist:
execution/__init__.py
services/__init__.py
tests/__init__.py
```

### Issue: Permission denied writing to /tmp

**Solution**: Create `tmp/` directory in project root.

```bash
mkdir -p tmp
```

## Next Steps

1. Read [README.md](../README.md) for project overview
2. Review example directive: [directives/example-directive.md](../directives/example-directive.md)
3. Study example script: [execution/example_script.py](../execution/example_script.py)
4. Review example tests: [tests/execution/test_example_script.py](../tests/execution/test_example_script.py)
5. Read [CLAUDE.md](c:\Users\ali_m\Downloads\CLAUDE.md) for agent operating model

## Getting Help

- Check [docs/](../docs/) directory for more guides
- Review test files for usage examples
- Read directive files for process documentation
- Ask senior developers for code review

## Code Quality Tools

### Format Code

```bash
# Format all Python files
black .

# Check what would change without modifying
black --check .
```

### Lint Code

```bash
# Run flake8
flake8 execution/ services/

# Run mypy for type checking
mypy execution/ services/
```

### Pre-commit Checks

Before committing code:

```bash
# Run tests
pytest

# Format code
black .

# Check linting
flake8 execution/ services/
```

## Daily Workflow

1. **Start of day**: Pull latest changes, activate venv
   ```bash
   git pull
   source venv/bin/activate
   ```

2. **Before coding**: Read relevant directives
   ```bash
   cat directives/relevant-directive.md
   ```

3. **While coding**: Run tests frequently
   ```bash
   pytest tests/execution/test_my_script.py
   ```

4. **Before committing**: Ensure all tests pass
   ```bash
   pytest
   black .
   ```

5. **End of day**: Update directives if behavior changed
   ```bash
   # Edit relevant directive to reflect learnings
   ```
