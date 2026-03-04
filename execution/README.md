# Execution

This directory contains deterministic tools and scripts that do the actual work.

## Purpose
Execution scripts are **Layer 3** - they perform the actual operations.

## Principles
Every script must be:
- **Repeatable**: Same inputs always produce same outputs
- **Testable**: Core logic can be unit tested
- **Auditable**: Clear what it does, with logging
- **Safe to rerun**: Idempotent where possible

## Rules
- One script = one clear responsibility
- Core logic must be importable (not just executable)
- No orchestration logic
- No AI prompts or LLM calls
- All I/O should be mockable for testing

## Structure
```python
# Good pattern:
def do_work(input_data):
    """Pure, testable logic"""
    return processed_data

def main():
    """CLI wrapper - handles I/O"""
    input_data = load_input()
    result = do_work(input_data)
    save_output(result)

if __name__ == "__main__":
    main()
```

## Testing
Every script should have:
- Unit tests in `/tests/execution/test_[script_name].py`
- Integration tests if it touches external systems
