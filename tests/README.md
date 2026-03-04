# Tests

Automated tests to protect correctness.

## Purpose
Testing is **mandatory**. Tests verify that execution scripts and workers behave correctly.

## Structure
Mirror the structure of what you're testing:
```
tests/
  execution/
    test_example_script.py
  services/
    test_worker.py
  integration/
    test_api_integration.py
```

## Types of Tests

### Unit Tests
- Test pure logic without I/O
- Mock all external dependencies
- Fast, deterministic, run locally
- Required for all non-trivial execution logic

### Integration Tests
- May touch dev sandboxes, test APIs, mock services
- Require explicit opt-in (env flag or CI label)
- Never touch production
- Test that components work together

### Worker Tests
- Test routing logic: correct scripts called for inputs
- Verify retries, idempotency, error handling
- Must never send real communications

## Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=execution --cov=services

# Run specific test file
pytest tests/execution/test_example.py

# Run integration tests (opt-in)
TEST_INTEGRATION=1 pytest tests/integration/
```

## Definition of Done
Tests must pass before any change is considered complete.
