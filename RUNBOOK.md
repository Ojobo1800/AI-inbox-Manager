# InboxGenius — Operations Runbook

---

## System Overview

| Component | What it does | Schedule / Port |
|-----------|-------------|-----------------|
| `execution/process_inbox_auto.py` | Fetches Gmail, classifies emails via GPT, moves to folders, logs to Google Sheets | Every **2 hours** via Windows Task Scheduler |
| `services/dashboard/api/` | FastAPI backend — serves stats, runs, settings | Port **8000** |
| `services/dashboard/frontend/` | React dashboard — shows stats, charts, countdown | Port **5173** |

**Log locations**

| Log | Path |
|-----|------|
| Processing runs | `logs/inbox_auto_YYYYMMDD.log` |
| Failure alerts | `logs/alerts.log` |
| Tmp output / summaries | `tmp/auto_process_YYYYMMDD_HHMMSS/summary.json` |
| Dashboard DB | `services/dashboard/api/email_dashboard.db` |

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
**Symptom:** Stats are all zero or "No data" charts

1. Confirm the backend is running: `curl http://localhost:8000/health`
2. Check `services/dashboard/api/email_dashboard.db` exists and has `process_runs` rows:
   ```bash
   sqlite3 services/dashboard/api/email_dashboard.db "SELECT COUNT(*) FROM process_runs;"
   ```
3. If DB is empty, trigger a manual run: right-click the Task Scheduler task → Run
4. If DB is missing, it is created automatically on first backend startup — restart the API

---

*Last updated: 2026-02-28 | Maintained by: Colaberry InboxGenius team*
