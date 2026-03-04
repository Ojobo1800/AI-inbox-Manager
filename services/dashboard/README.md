# Email Management Dashboard

Web-based dashboard for managing and approving email classifications in the Colaberry email processing system.

## Features

- **Approval Queue**: Review and approve emails with low confidence classifications
- **Inbox Monitor**: Real-time view of current inbox state
- **Manual Actions**: Manually classify, move, or delete emails
- **Statistics Dashboard**: Processing metrics and trends
- **Whitelist Management**: Manage protected companies
- **Audit Trail**: Complete history of all actions

## Architecture

### Backend (FastAPI)
- RESTful API for email management
- PostgreSQL database for email metadata
- Session-based authentication with bcrypt
- Server-Sent Events (SSE) for real-time updates
- Integration with existing execution scripts

### Frontend (React + TypeScript)
- Modern responsive UI with TailwindCSS
- Real-time updates via SSE
- React Query for state management
- Mobile-friendly design

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+ (or use Docker)
- Node.js 18+ (for frontend)
- Existing email processing setup (`.env` with IMAP credentials)

### 1. Set Up Database

**Option A: Using Docker (Recommended)**
```bash
cd services/dashboard
docker-compose up -d postgres
```

**Option B: Local PostgreSQL**
```bash
createdb email_dashboard
```

### 2. Configure Environment

```bash
cd services/dashboard/api

# Copy example env file
cp .env.example .env

# Generate admin password hash
python ../scripts/generate_password_hash.py

# Add the generated hash to .env
# ADMIN_PASSWORD_HASH=<paste hash here>
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
# Database tables will be created automatically on first run
python main.py
```

### 5. Start Backend

**Option A: Direct Python**
```bash
python main.py
# API will be available at http://localhost:8000
```

**Option B: Using Docker**
```bash
cd services/dashboard
docker-compose up
```

### 6. Test Backend

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Authentication

The dashboard uses simple password authentication with session cookies.

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}' \
  -c cookies.txt

# Session cookie will be stored in cookies.txt
```

**Access Protected Endpoints:**
```bash
curl http://localhost:8000/api/test/protected \
  -b cookies.txt
```

**Logout:**
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -b cookies.txt
```

## Database Schema

### Core Tables

- **emails**: Email metadata and content
- **classifications**: AI classification results
- **approvals**: Human review and approval records
- **process_runs**: Automated processing statistics
- **whitelist_companies**: Protected companies (never moved/deleted)
- **email_actions**: Audit trail of all actions
- **user_sessions**: Active authentication sessions
- **system_config**: Runtime configuration

See [models.py](api/models.py) for complete schema definitions.

## Integration with Existing System

The dashboard integrates with the existing email processing system:

### File-Based Integration (Current)

1. `process_inbox_auto.py` runs hourly (Windows Task Scheduler)
2. Writes `tmp/auto_process_<timestamp>/summary.json`
3. Dashboard imports these files into database
4. Dashboard provides manual oversight and actions

### Manual Actions

Dashboard can trigger existing execution scripts:
- `fetch_emails.py` - Fetch current inbox state
- `classify_email.py` - Re-classify emails
- `move_emails()` - Move emails to folders
- `delete_emails()` - Delete spam emails

## Development

### Project Structure

```
services/dashboard/
├── api/                        # Backend (FastAPI)
│   ├── main.py                # App entry point
│   ├── config.py              # Configuration
│   ├── database.py            # DB connection
│   ├── models.py              # SQLAlchemy models
│   ├── auth.py                # Authentication
│   ├── routers/               # API endpoints (future)
│   └── integration/           # Execution script wrappers (future)
├── frontend/                  # Frontend (React) (future)
├── tests/                     # Tests
├── scripts/                   # Helper scripts
├── docker-compose.yml         # Docker services
└── README.md                  # This file
```

### Running Tests

```bash
cd services/dashboard/api
pytest
```

### Code Style

```bash
# Format code
black .

# Lint code
flake8 .
```

## Deployment

### Cloud Deployment (Production)

Recommended platforms:
- **Render**: https://render.com
- **Railway**: https://railway.app
- **Heroku**: https://heroku.com

See [DASHBOARD_DEPLOYMENT.md](../../docs/DASHBOARD_DEPLOYMENT.md) (to be created) for detailed deployment instructions.

### Environment Variables (Production)

```bash
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=<postgresql-connection-string>
SESSION_SECRET=<generate-random-secret>
ADMIN_PASSWORD_HASH=<bcrypt-hash>
CORS_ORIGINS=https://yourdomain.com
```

## Security Considerations

- Passwords hashed with bcrypt (cost factor 12)
- Session tokens are UUIDs in HTTP-only cookies
- Sessions expire after 24 hours of inactivity
- Rate limiting: 100 requests/minute per IP
- CORS restricted to configured origins
- Email credentials stored in `.env` file (not in database)
- All actions logged for audit trail

## Monitoring

### Logs

Logs are written to stdout in structured format:
```
2024-01-28 10:30:15 - main - INFO - User admin logged in successfully
```

In production, configure log aggregation (e.g., CloudWatch, DataDog).

### Metrics

Track the following metrics:
- API endpoint response times
- Database query performance
- Active sessions count
- Email processing throughput
- Approval queue size

## Troubleshooting

### Database Connection Failed

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Test connection
psql postgresql://postgres:postgres@localhost:5432/email_dashboard
```

### Authentication Not Working

```bash
# Verify ADMIN_PASSWORD_HASH is set in .env
grep ADMIN_PASSWORD_HASH .env

# Regenerate password hash if needed
python ../scripts/generate_password_hash.py
```

### Import Error

```bash
# Ensure you're in the api directory
cd services/dashboard/api

# Verify Python path includes current directory
export PYTHONPATH=.
```

## Next Steps

### Phase 2: Integration Layer (In Progress)
- [ ] Create integration wrappers for execution scripts
- [ ] Implement summary.json file importer
- [ ] Build email sync service (IMAP → Database)
- [ ] Create API endpoints for manual actions

### Phase 3: Core API (Upcoming)
- [ ] Implement approval queue endpoints
- [ ] Implement inbox monitoring endpoints
- [ ] Implement statistics endpoints
- [ ] Implement SSE event stream
- [ ] Implement whitelist management endpoints

### Phase 4: Frontend (Upcoming)
- [ ] Set up React + TypeScript + Vite
- [ ] Implement authentication UI
- [ ] Implement approval queue page
- [ ] Implement inbox monitor page
- [ ] Implement statistics dashboard
- [ ] Implement settings page

## Support

For issues or questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review API docs at http://localhost:8000/docs
3. Check application logs
4. Review the [plan file](../../.claude/plans/composed-weaving-origami.md)

## License

Internal use only - Colaberry Novedea AI Projects
