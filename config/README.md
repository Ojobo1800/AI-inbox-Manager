# Config

This directory contains environment-specific configuration.

## Purpose
- Environment wiring (dev vs staging vs prod identifiers)
- Feature flags
- Non-secret configuration values

## Rules
- **NO SECRETS ALLOWED**
- Use environment variables for secrets
- Create `.env.example` to document required env vars
- Configs should be JSON or TOML for easy parsing

## Structure
```
config/
  dev.json       # Development environment
  staging.json   # Staging environment
  prod.json      # Production (committed, no secrets)
  .env.example   # Template for required secrets
```

## Example
```json
{
  "environment": "dev",
  "api_base_url": "https://api-dev.example.com",
  "log_level": "DEBUG",
  "retry_attempts": 3
}
```

## Secrets Management
Never commit:
- API keys
- Passwords
- Database credentials
- OAuth tokens
- Private keys

Use `.env` file locally (gitignored) with python-dotenv.
