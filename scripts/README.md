# Utility Scripts

Helper scripts for common development tasks.

## Setup Scripts

### `setup.sh` / `setup.bat`
Complete development environment setup for new developers.

**Usage**:
```bash
# Mac/Linux
bash scripts/setup.sh

# Windows
scripts\setup.bat
```

**What it does**:
- Checks Python version
- Creates virtual environment
- Installs dependencies
- Creates `.env` from template
- Creates `tmp/` directory
- Runs tests to verify setup

## Testing Scripts

### `test.sh` / `test.bat`
Run all tests with coverage reporting.

**Usage**:
```bash
# Mac/Linux
bash scripts/test.sh

# Windows
scripts\test.bat
```

**What it does**:
- Runs pytest with coverage
- Generates HTML coverage report
- Shows coverage summary in terminal

**Output**: Coverage report in `htmlcov/index.html`

## Code Quality Scripts

### `lint.sh`
Run all linting and type checking tools.

**Usage**:
```bash
bash scripts/lint.sh
```

**What it does**:
- Checks code formatting with black
- Runs flake8 linting
- Runs mypy type checking

**Note**: Exits with error if any check fails

### `format.sh`
Auto-format all Python code.

**Usage**:
```bash
bash scripts/format.sh
```

**What it does**:
- Formats all Python files with black
- Applies consistent code style

**Note**: Modifies files in place

## Making Scripts Executable

On Mac/Linux, you may need to make scripts executable:

```bash
chmod +x scripts/*.sh
```

## Adding New Scripts

When adding new utility scripts:

1. Create both `.sh` (Mac/Linux) and `.bat` (Windows) versions
2. Add clear comments explaining what the script does
3. Use `set -e` in bash scripts to exit on errors
4. Document the script in this README
5. Test on both platforms if possible

## Common Workflows

### First Time Setup
```bash
# Clone repo, then:
bash scripts/setup.sh
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

### Before Committing
```bash
# Format code
bash scripts/format.sh

# Run tests
bash scripts/test.sh

# Check linting
bash scripts/lint.sh
```

### Daily Development
```bash
# Activate environment
source venv/bin/activate

# Run tests frequently
bash scripts/test.sh
```
