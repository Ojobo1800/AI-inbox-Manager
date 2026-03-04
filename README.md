# Colaberry Agent Project

An agent-first, deterministic-execution system following the Colaberry operating model.

## Overview

This project separates concerns into three layers:

1. **Directives** (What to do) - Human-readable SOPs in `/directives`
2. **Orchestration** (Decision making) - Claude Code as the planning agent
3. **Execution** (Doing the work) - Deterministic scripts in `/execution`

**Core Principle**: LLMs are probabilistic. Production systems must be deterministic.

Claude reasons, plans, and orchestrates. Scripts execute business logic.

## Project Structure

```
.
├── agents/          # Agent personas and role definitions
├── directives/      # SOPs and runbooks (what to do)
├── execution/       # Deterministic scripts (how to do it)
├── services/        # Runtime workers and scheduled jobs
├── config/          # Environment configuration (no secrets)
├── tests/           # Automated tests (unit + integration)
├── docs/            # Documentation and setup guides
└── tmp/             # Scratch space (never committed)
```

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Or install with dev dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# Never commit .env to version control!
```

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=execution --cov=services --cov-report=html

# Run specific test file
pytest tests/execution/test_example_script.py

# Run integration tests (requires opt-in)
TEST_INTEGRATION=1 pytest tests/integration/
```

### 4. Run Example Script

```bash
# Create sample input
echo '[{"id": "1", "value": 10}, {"id": "2", "value": 20}]' > tmp/input.json

# Run example script
python execution/example_script.py tmp/input.json tmp/output.json

# Check results
cat tmp/output.json
```

## Development Workflow

### Before Making Changes

1. Read relevant directives in `/directives`
2. Understand the goal and constraints
3. Plan your approach

### Making Changes

1. Implement logic in `/execution` scripts
2. Write/update tests in `/tests`
3. Update relevant directives
4. Ensure tests pass

### Definition of Done

A change is complete when:
- [ ] Relevant unit tests exist and pass
- [ ] Behavior-changing logic updates directives
- [ ] No secrets are introduced
- [ ] Changes are understandable by a junior developer
- [ ] Code follows the layer separation model

## Layer Responsibilities

### Directives (`/directives`)
- Define goals and steps
- Document edge cases
- Reference execution scripts
- No executable code

### Execution (`/execution`)
- Deterministic, testable scripts
- One script = one clear responsibility
- Core logic separated from I/O
- No orchestration logic

### Services (`/services`)
- Long-running workers
- Call execution scripts
- Handle scheduling, retries, queuing
- No business logic

## Testing Strategy

### Unit Tests
- Test pure logic without I/O
- Mock external dependencies
- Fast, deterministic, local

### Integration Tests
- May touch dev sandboxes
- Require `TEST_INTEGRATION=1` environment variable
- Never touch production

### Worker Tests
- Verify routing logic
- Test retries and error handling
- Mock communications

## Safety Rules

- No production writes without explicit environment checks
- No secrets in repository
- No destructive operations without confirmation
- All changes must be reviewable and understandable

## Agent Operating Model

See [CLAUDE.md](c:\Users\ali_m\Downloads\CLAUDE.md) for complete Claude Code operating rules.

Key principles:
- Claude reads directives before acting
- Never mix layers
- Prefer deterministic tools
- Self-annealing: failures improve the system

## Common Tasks

### Adding a New Feature

1. Create or update directive in `/directives`
2. Implement execution script in `/execution`
3. Write tests in `/tests/execution`
4. Update this README if needed

### Running Scheduled Jobs

Workers in `/services` can run scheduled jobs:

```python
from execution.my_script import my_function

def worker():
    # Worker handles scheduling
    result = my_function(data)  # Calls deterministic script
    return result
```

### Adding Configuration

1. Add to appropriate config file in `/config`
2. Add to `.env.example` if it's a secret
3. Never commit actual secrets

## Troubleshooting

### Tests Failing

```bash
# Run tests with verbose output
pytest -v

# Run specific test
pytest tests/execution/test_example_script.py::TestProcessData::test_process_valid_records

# See coverage report
pytest --cov=execution --cov-report=term-missing
```

### Import Errors

Make sure you've installed the package in development mode:

```bash
pip install -e .
```

### Environment Issues

Check your Python version and virtual environment:

```bash
python --version  # Should be 3.9+
which python      # Should point to venv
```

## Contributing

1. Read the relevant directive first
2. Make focused, single-purpose changes
3. Write tests
4. Update documentation
5. Get review from senior developer

## Resources

- [Project Setup Guide](docs/README.md)
- [Testing Guide](tests/README.md)
- [CLAUDE.md](c:\Users\ali_m\Downloads\CLAUDE.md) - Full operating model

## License

[Your License Here]
