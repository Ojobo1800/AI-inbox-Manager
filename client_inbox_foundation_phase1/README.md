# Client Project - Phase 1 Foundation

## Goal
Set up the infrastructure baseline for an AI-powered inbox system before introducing AI logic.

## What Is Included
- FastAPI service skeleton
- `GET /health` endpoint
- Gmail webhook route: `POST /webhooks/gmail`
- Gmail Pub/Sub payload decoding and validation
- Gmail watch registration script
- SQL Server checkpoint persistence (`gmail_sync_checkpoint`)
- SQL Server unread intake persistence (`gmail_unread_intake`)
- SQL Server interview tracker persistence (`interview_tracker`)
- Google Sheets append for interview tracker rows
- Google OAuth routes for user sign-in:
  - `GET /auth/google/login`
  - `POST /auth/google/exchange`
- Incremental Gmail sync route:
  - `POST /sync/gmail/incremental`
- Deterministic interview record mapping layer
- Twilio WhatsApp client stub
- JSON logging setup
- VS Code workspace settings
- Tests

## Quick Start (Windows PowerShell)
```powershell
cd client_inbox_foundation_phase1
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.phase1.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

## Google OAuth Flow (separate frontend)
1. Frontend sends user to: `GET /auth/google/login`
2. Google redirects to your frontend callback (`GOOGLE_OAUTH_REDIRECT_URI`)
3. Frontend sends authorization code to backend:
   - `POST /auth/google/exchange` with JSON `{ "code": "..." }`
4. Backend exchanges code with Google and returns tokens/profile JSON.

## Register Gmail Watch
```powershell
.\.venv\Scripts\python scripts\register_gmail_watch.py
```

## Incremental Sync from Checkpoint
Trigger deterministic unread interview extraction + dual writes:

```powershell
Invoke-RestMethod \
  -Method Post \
  -Uri http://127.0.0.1:8000/sync/gmail/incremental \
  -ContentType 'application/json' \
  -Body '{"email_address":"student@yourdomain.com"}'
```

What it does:
- Loads `history_id` from `gmail_sync_checkpoint`
- Calls Gmail `history.list` for message deltas
- Pulls new messages and filters for `UNREAD` + interview-related keywords
- Stores raw normalized emails in `gmail_unread_intake`
- Maps each message to a structured interview record
- Upserts structured records into `interview_tracker`
- Appends structured rows to Google Sheets (`GOOGLE_SHEET_ID` + `GOOGLE_SHEET_WORKSHEET`)
- Advances checkpoint to latest `history_id`

## Validate
- Open `http://127.0.0.1:8000/health`
- Run tests: `.\.venv\Scripts\python -m pytest`
- Send a test push request to `/webhooks/gmail` with Pub/Sub envelope body

## Notes
- For Google Workspace, set `GOOGLE_WORKSPACE_USER` for domain-wide delegation.
- `GOOGLE_PUBSUB_VERIFICATION_TOKEN` is enforced when configured.
- Ensure SQL Server has network access and ODBC Driver 18 installed.
- Keep OAuth client secret only in environment variables, never in repo.
