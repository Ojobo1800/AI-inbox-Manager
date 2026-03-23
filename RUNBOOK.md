# InboxGenius — Operations Runbook

---

## System Overview

| Component | What it does | Where |
|-----------|-------------|-------|
| `execution/process_inbox_auto.py` | Fetches Gmail, classifies emails via GPT, moves to folders, writes to Railway DB | Every **2 hours** via Windows Task Scheduler (local) |
| `services/dashboard/api/` | FastAPI backend — serves stats, runs, settings | **Railway**: `inboxgenius-api-production.up.railway.app` / local port **8000** |
| `services/dashboard/frontend/` | React dashboard — shows stats, charts, countdown | **Vercel**: `ai-inbox-manager-vert.vercel.app` / local port **5173** |
| `inboxgenius-db` | PostgreSQL database — stores all ProcessRun records | **Railway** (shared between local scheduler and cloud API) |

**Log locations**

| Log | Path |
|-----|------|
| Processing runs | `logs/inbox_auto_YYYYMMDD.log` |
| Failure alerts | `logs/alerts.log` |
| Tmp output / summaries | `tmp/auto_process_YYYYMMDD_HHMMSS/summary.json` |
| Local Dashboard DB | `services/dashboard/api/email_dashboard.db` (backup only) |
| Cloud Dashboard DB | Railway PostgreSQL — `inboxgenius-db` service |

---

## Restart Instructions

### Backend API
```bash
cd services/dashboard/api
uvicorn main:app --host 0.0.0.0 --port 8000
```
Verify: http://localhost:8000/health → `{"status":"healthy"}`

### Frontend
```bash
cd services/dashboard/frontend
npm run dev
```
Access: http://localhost:5173  Login: `admin` / `admin123`

### Scheduled Task (Windows Task Scheduler)
1. Open **Task Scheduler** → Task Scheduler Library
2. Find task: **"InboxGenius Auto Process"** (or similar)
3. Right-click → **Run** to trigger immediately, or **Enable** if disabled
4. Script invoked: `python execution/process_inbox_auto.py`
5. Task interval: every 2 hours, starting from last run time

---

## Lock Recovery

**Lock file:** `tmp/process.lock`

The lock prevents overlapping runs. It is written at startup and deleted on clean exit.

**When to delete it:**
- A run crashed mid-flight (check `logs/inbox_auto_YYYYMMDD.log` for FATAL or traceback)
- Task Scheduler shows the task as "Running" but no Python process is active
- Lock is more than 3 hours old

```bash
# Check lock contents (PID + timestamp)
cat tmp/process.lock

# Verify the PID is not a live process (Windows)
tasklist | findstr <PID>

# If process is dead, delete the lock
del tmp\process.lock
```

---

## Credential Rotation

### OpenAI API Key
1. Go to https://platform.openai.com/api-keys → create new key
2. Open `.env` in project root
3. Replace `OPENAI_API_KEY=sk-proj-...` with the new key
4. No restart needed — key is read fresh each run

### Gmail OAuth Token (`config/gmail_token.json`)
The token auto-refreshes using the stored refresh token. Manual rotation is only needed if access is fully revoked.

1. Delete `config/gmail_token.json`
2. Run: `python execution/gmail_auth.py`
3. A browser window opens — sign in as `c_interviews@colaberry.com` and grant access
4. New `gmail_token.json` is written automatically
5. Verify: `python -c "from execution.gmail_auth import get_access_token; print(get_access_token()[:20])"`

### Google Sheets Service Account (`config/service-account-key.json`)
1. Google Cloud Console → IAM & Admin → Service Accounts
2. Select `inboxgenius-sheets@ai-inbox-manager-agent.iam.gserviceaccount.com`
3. Keys → Add Key → JSON → download
4. Replace `config/service-account-key.json` with the new file
5. Ensure the sheet `183B555Fg3ghmqvZPJLGM2O3vGYLrXCDXXcAcSqe3F9M` is still shared with the service account email

---

## Failure Playbook

### Cost Guardrail Triggers Repeatedly
**Symptom:** Alerts with subject `[InboxGenius] Run aborted — cost guardrail` or `Cost guardrail triggered — Gmail moves SKIPPED`

1. Check `logs/inbox_auto_YYYYMMDD.log` for the estimated/actual cost values
2. Open `.env` → adjust `COST_GUARDRAIL_USD` upward if the inbox is legitimately larger
3. If a large spam batch caused it: manually clear the inbox first, then re-enable
4. Check OpenAI usage dashboard for unexpected spikes — could indicate a prompt regression

### OpenAI Fails Continuously
**Symptom:** Log shows repeated `GPT classification failed` or HTTP 429/500 errors

1. Check https://status.openai.com for an outage — if so, wait and Task Scheduler retries in 2 hours
2. If 429 (rate limit): reduce `EMAIL_BATCH_SIZE` in the dashboard Settings page (default: 50 → try 20)
3. If 401 (invalid key): rotate OpenAI key (see above)
4. Classifications will be skipped for affected emails — they remain in INBOX for the next run

### Gmail OAuth Expires / IMAP Access Fails
**Symptom:** Log shows `AUTHENTICATE failed` or `invalid_grant` in the OAuth flow

1. Check if Google forced a token revocation (password change, security event, or > 6 months inactive)
2. Rotate the Gmail OAuth token (see above)
3. If revocation was due to a policy change, re-authorise the OAuth app in Google Cloud Console
4. SMTP alert sending will also fail during this window — check `logs/alerts.log` for the fallback record

### Dashboard Shows No Data
**Symptom:** Stats are all zero or "No data" charts on cloud dashboard

1. Confirm Railway backend is running: `curl https://inboxgenius-api-production.up.railway.app/health`
2. Confirm `DATABASE_URL` in `.env` points to Railway PostgreSQL (not local SQLite)
3. Trigger a manual run: right-click Task Scheduler task → **Run** — check logs for `Dashboard ProcessRun record created`
4. If Railway DB is empty, run the migration script:
   ```bash
   # From project root — copies all local ProcessRun records to Railway
   python -c "
   import sys; sys.path.insert(0, 'services/dashboard/api')
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   from models import ProcessRun
   local_db = sessionmaker(bind=create_engine('sqlite:///services/dashboard/api/email_dashboard.db'))()
   remote_db = sessionmaker(bind=create_engine('postgresql://postgres:yqtPrlHdOjxcYIIfznlSqBqYkAlVJXbu@centerbeam.proxy.rlwy.net:56433/railway'))()
   existing = {r.run_timestamp for r in remote_db.query(ProcessRun).all()}
   added = 0
   for r in local_db.query(ProcessRun).all():
       if r.run_timestamp not in existing:
           remote_db.add(ProcessRun(run_timestamp=r.run_timestamp, total_emails=r.total_emails, interview_requests=r.interview_requests, organized=r.organized, spam_deleted=r.spam_deleted, categories_breakdown=r.categories_breakdown, duration_seconds=r.duration_seconds, status=r.status))
           added += 1
   remote_db.commit()
   print(f'Migrated {added} records')
   "
   ```

---

---

## Dashboard Logins

**Cloud URL (stakeholder access):** https://ai-inbox-manager-vert.vercel.app
**Local URL (admin):** http://localhost:5173

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Admin | `admin` | `admin123` | Full access |
| Stakeholder | any (e.g. `stakeholder`) | `stakeholder123` | View-only |

To change a password in **cloud (Railway)**:
1. Generate new hash: `python -c "from services.dashboard.api.auth import hash_password; print(hash_password('newpassword'))"`
2. Go to Railway → **inboxgenius-api** → **Variables** → **Raw Editor**
3. Update `ADMIN_PASSWORD_HASH` or `STAKEHOLDER_PASSWORD_HASH` on a **single line** (no line breaks)
4. Save — Railway redeploys automatically

To change a password **locally**:
1. Generate hash as above
2. Open `services/dashboard/api/.env`
3. Replace the relevant hash value
4. Restart the backend

---

## Processing Performance Settings

Current settings (optimised 2026-03-22):

| Setting | Value | File |
|---------|-------|------|
| GPT Model | `gpt-4o-mini` | `execution/classify_email.py` |
| Max tokens | `800` | `execution/classify_email.py` |
| Parallel workers | `16` | `execution/process_inbox_auto.py` |
| Batch size (fetch limit) | `MAX_EMAILS_PER_RUN` env var (default 100) | `.env` |

Expected run duration: **~30–60 seconds** per batch of 50 emails.

### Clear Email Backlog Manually
If unread emails pile up (e.g. after system downtime):
```bash
cd "C:\Users\lhc22\OneDrive\Desktop\AI_Ibox_Genuis_Manager\Colaberry_InboxGenius-main"
python tmp/clear_backlog.py
```
Runs batches of 50 until inbox is empty. Press `Ctrl+C` to stop safely at any time.

---

## Git & GitHub

**Repository:** https://github.com/Ojobo1800/AI-inbox-Manager

### Commit and Push Changes
Run from the project root:
```bash
cd "C:\Users\lhc22\OneDrive\Desktop\AI_Ibox_Genuis_Manager\Colaberry_InboxGenius-main"
git add .
git commit -m "your message here"
git push
```

### Check What Has Changed (before committing)
```bash
git status
git diff
```

### View Commit History
```bash
git log --oneline -10
```

### Files Never Committed (secrets — protected by .gitignore)
- `config/gmail_token.json`
- `config/gmail_credentials.json`
- `config/service-account-key.json`
- `.env`
- `*.db` (database files)
- `logs/` (log files)

---

## Cloud Deployment (Railway + Vercel)

| Service | Platform | URL |
|---------|----------|-----|
| Frontend | Vercel | https://ai-inbox-manager-vert.vercel.app |
| Backend API | Railway | https://inboxgenius-api-production.up.railway.app |
| PostgreSQL DB | Railway | `inboxgenius-db` service |

### Key Railway Environment Variables (inboxgenius-api)
| Variable | Purpose |
|----------|---------|
| `ADMIN_PASSWORD_HASH` | bcrypt hash of admin password |
| `STAKEHOLDER_PASSWORD_HASH` | bcrypt hash of stakeholder password |
| `CORS_ORIGINS` | Must match Vercel frontend URL exactly (no trailing slash) |
| `DATABASE_PUBLIC_URL` | Auto-set by Railway — PostgreSQL connection string |
| `SESSION_SECRET` | Random secret for session tokens |
| `ENVIRONMENT` | Set to `production` |

### How Live Data Flows
1. Windows Task Scheduler runs `process_inbox_auto.py` every 2 hours
2. Script reads `DATABASE_URL` from `.env` → writes ProcessRun to **Railway PostgreSQL**
3. Stakeholder opens Vercel URL → frontend calls Railway API → reads from Railway PostgreSQL
4. Dashboard updates automatically after each scheduler run

> **Note:** Laptop must be on for data to flow. Processing does not run on Railway.

---

*Last updated: 2026-03-22 | Maintained by: Colaberry InboxGenius team*
