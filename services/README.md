# Services

Long-running or scheduled jobs (optional).

## Purpose
This directory contains the **runtime system** - workers, schedulers, and services.

## Relationship to Execution
Services/workers **call** execution scripts. They don't reimplement logic.

```python
# Good: Worker calls execution script
from execution.process_data import process_data

def worker():
    while True:
        job = queue.get()
        result = process_data(job.data)  # Calls deterministic script
        queue.complete(job, result)
```

## Common Patterns
- Background workers (queue processors)
- Scheduled jobs (cron-like)
- API servers
- Event listeners

## Rules
- Workers orchestrate; scripts execute
- All business logic belongs in `/execution`
- Workers handle:
  - Job queuing
  - Retries
  - Error handling
  - Scheduling
  - Inter-service communication

## Testing
Worker tests verify routing logic:
- Given inputs → correct execution scripts are called
- Retries work correctly
- Idempotency is maintained
- No real communications during tests
