# InboxGenius — LinkedIn Demo Video
## Production Guide & Shot-by-Shot Script
**Target length:** 90 seconds | **Format:** Screen recording + voiceover

---

## BEFORE YOU RECORD

### Setup checklist
- [ ] Start the backend: `
`
- [ ] Start the frontend: `cd services/dashboard/frontend && npm run dev`
- [ ] Open browser at `http://localhost:5173` — log in as admin
- [ ] Set browser zoom to **90%** so all cards are visible
- [ ] Close all other browser tabs
- [ ] Use **Loom** (free), **OBS**, or Windows **Clipchamp** (Win+G) to record
- [ ] Record at 1920×1080 — full screen, no taskbar visible
- [ ] Silence your phone. No notifications during recording.
- [ ] Do a 30-second practice run before the real take

### Voice tone
Calm, confident, and natural — like you're showing a colleague.
Not a sales pitch. Not robotic. Speak at 80% of your normal speed.

---

## SHOT-BY-SHOT SCRIPT

---

### SCENE 1 — HOOK (0:00 – 0:07)
**Screen:** Static black screen with white text (add in editing):
> *"6 hours of manual inbox work. Every. Single. Day."*

**Narration (say out loud):**
> "Before I built this — a real placement team was spending six hours a day triaging interview emails manually. Spreadsheets. Copy-paste. Human availability as a bottleneck."

**On-screen text overlay to add in editing:**
- "6 hrs/day → 0" in bold at the end of scene

---

### SCENE 2 — DASHBOARD OVERVIEW (0:07 – 0:22)
**Screen action:** Dashboard home page fully loaded. Mouse hovers slowly across the 5 stat cards from left to right: Emails Today → Interview Requests → Pending Approvals → This Week → In Inbox.

**Narration:**
> "This is InboxGenius — an AI pipeline I built at Colaberry that processes the interview inbox automatically, every two hours, around the clock. Right here on the dashboard, you can see in real time: emails processed today, interview requests detected, what's pending approval, and what's sitting live in the inbox right now."

**On-screen text overlays (add in editing):**
- Arrow pointing to "Emails Today" → label: *"Auto-processed every 2 hrs"*
- Arrow pointing to "Interview Requests" → label: *"AI-detected, zero manual triage"*

---

### SCENE 3 — AI COST & ENGINEERING KPIS (0:22 – 0:32)
**Screen action:** Scroll down slightly to reveal the 3 engineering KPI cards (AI Cost Today, Avg Duration, Failure Rate %).

**Narration:**
> "The system tracks its own cost — every GPT call is metered. You can see the average processing duration and failure rate over the last seven days. This was a design requirement: full auditability, cost guardrails built in."

**On-screen text overlay:**
- Highlight AI Cost card → *"GPT-4o-mini cost per run tracked to the cent"*

---

### SCENE 4 — CATEGORY BREAKDOWN CHART (0:32 – 0:44)
**Screen action:** Scroll to the Category Breakdown donut chart. Let it sit for 2 seconds. Then slowly move the mouse over each segment to trigger the Recharts tooltip — hover over Interview Request, then Rejection, then Offer.

**Narration:**
> "Every email is classified into one of twenty-six categories by GPT-4o-mini. On this chart you can see the distribution across the categories that matter most to a placement team — interview requests, rejections, reschedules, schedules, and offers. Each one routes automatically to the right Gmail folder."

**On-screen text overlay:**
- *"26 categories | Classified in parallel | ~$0.015/email"*

---

### SCENE 5 — RUN PROCESSING LIVE (0:44 – 1:00)
**Screen action:**
1. Scroll back to top
2. Click the **"Run Now"** button (top right of dashboard)
3. The button shows a spinning icon — let it run for a few seconds
4. When it completes, the toast message appears ("Done — X emails processed")
5. Watch the stat cards update live

**Narration:**
> "Watch what happens when I trigger a run manually. The system connects to Gmail via OAuth2, fetches every unread email, fires parallel GPT classification calls with sixteen workers, applies business rules, moves emails to folders, and updates the dashboard — all in under two minutes. Normally this fires on a schedule every two hours, automatically."

**On-screen text overlay:**
- During spin: *"Gmail IMAP → OAuth2 → GPT-4o-mini → PostgreSQL → Dashboard"*
- After success toast: *"Done. Zero manual work."*

---

### SCENE 6 — INTERVIEW EVENTS REPORT (1:00 – 1:10)
**Screen action:** Click the **"Interview Events Report"** banner. The report page loads. Scroll slowly through the table showing interview events with company names, student names, and notification status columns.

**Narration:**
> "Every interview email that comes in creates a structured event record — company, position, student, notification status. The placement team can see at a glance who was notified, when, and whether it's still pending."

**On-screen text overlay:**
- *"Structured audit trail. Every interview. Every student."*

---

### SCENE 7 — REPORTS PAGE (1:10 – 1:20)
**Screen action:** Navigate to the **Reports** page from the sidebar. Click through the tabs quickly: Weekly Summary (pause 1 sec) → Interview Pipeline (pause 1 sec) → Student Activity (pause 1 sec) → Company Tracker (pause 1 sec).

**Narration:**
> "The reports layer gives management a full picture — weekly pipeline stats, student activity, which companies are sending the most opportunities, and any missed notifications that need follow-up."

**On-screen text overlay:**
- *"Weekly Summary | Pipeline | Students | Companies | Missed Alerts"*

---

### SCENE 8 — IMPACT CLOSE (1:20 – 1:28)
**Screen:** Return to the Dashboard home page. Let it sit, fully loaded.

**Narration:**
> "Six hours of daily manual work — down to zero. Student notifications that used to take a full day now arrive within minutes of the email landing. Built with Python, FastAPI, React, PostgreSQL, and OpenAI."

**On-screen text overlay (large, centered — add in editing):**
```
6 hrs/day manual work  →  0
Next-day notifications  →  < 2 minutes
Cost per run            →  ~$1.00
```

---

### SCENE 9 — CLOSING CARD (1:28 – 1:35)
**Screen:** Fade to a simple dark card (add in editing) with:
```
InboxGenius
Built by [Your Name]
Python · FastAPI · React · OpenAI · PostgreSQL

Open to Senior Data/ML/Software Engineering roles
judeojobo@gmail.com
```

**Narration:**
> "If you're building AI-powered operations tools or working on automation in staffing, placement, or HR-tech — I'd love to connect."

---

## EDITING CHECKLIST (post-recording)

Use **Clipchamp** (free, built into Windows 11 — press Win+G) or **DaVinci Resolve** (free):

1. **Trim** any hesitations or awkward pauses
2. **Add text overlays** from each scene above (white bold text, bottom third of screen)
3. **Add subtle background music** — search "corporate background music no copyright" on YouTube Audio Library. Keep volume at ~15% so voice is clear
4. **Speed ramp** Scene 5 (the run processing) if it takes longer than 15 seconds — speed up to 2× during the wait, cut back to 1× when the toast appears
5. **Color grade**: Slight brightness boost (+10), slight saturation boost (+15) — makes the dashboard pop
6. **Captions**: Add auto-captions (Clipchamp does this automatically) — 85% of LinkedIn video is watched on mute
7. **Export at 1080p, MP4**

---

## LINKEDIN POST COPY (paste this with the video)

```
I built an AI system that eliminated 6 hours of daily manual inbox work.

Here's how InboxGenius works:

→ Connects to Gmail via IMAP + OAuth2
→ GPT-4o-mini classifies every unread email (26 categories)
→ Moves emails to the right folders automatically
→ Creates structured interview event records
→ Notifies students within minutes — not next day
→ Logs every run: cost, duration, failure rate, classification breakdown
→ Runs every 2 hours on a schedule, zero human input required

Tech stack: Python · FastAPI · React · PostgreSQL · OpenAI · Railway · Vercel

The hardest part wasn't the AI. It was building trust into automation:
cost guardrails, audit trails, and missed-notification alerts so the team
could hand off inbox management without anxiety.

Manual inbox work: 6 hrs/day → 0
Student notifications: next-day → < 2 min
Cost per run: ~$1.00

Built while working at @Colaberry.

Open to senior data engineering, ML engineering, or backend roles.
Drop a comment or DM if you're working on similar problems.

#Python #FastAPI #React #OpenAI #Automation #AIEngineering #Colaberry
```

---

## QUICK RECORDING TIPS

- **Keep the mouse moving slowly** — fast mouse = looks nervous on video
- **Hover over things** before clicking — gives viewers time to read
- **Don't rush the stat cards section** — those numbers are your proof of work
- **If you stumble** — pause 2 seconds and re-say the line. Easy to edit out.
- **Best time to record**: morning, quiet environment, after a coffee
- **Record 2-3 takes** — pick the best one. Takes 5 minutes per take.
