"""Test stats calculation."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Create database session
engine = create_engine('sqlite:///email_dashboard.db')
Session = sessionmaker(bind=engine)
db = Session()

# Import models
import sys
sys.path.insert(0, 'api')
from models import ProcessRun

# Get current time
now = datetime.utcnow()
print(f"Current UTC time: {now}")
print()

# Calculate today_start
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
print(f"Today start: {today_start}")
print()

# Query today's runs
today_runs = db.query(ProcessRun).filter(
    ProcessRun.run_timestamp >= today_start
).all()

print(f"Today's runs: {len(today_runs)}")
for run in today_runs:
    print(f"  Run {run.id}: {run.run_timestamp} - {run.total_emails} emails, {run.interview_requests} interviews")
print()

# Calculate today's totals
today_total = sum(r.total_emails for r in today_runs)
today_interview = sum(r.interview_requests for r in today_runs)
today_organized = sum(r.organized for r in today_runs)
today_spam = sum(r.spam_deleted for r in today_runs)

print(f"Today's totals:")
print(f"  Total emails: {today_total}")
print(f"  Interview requests: {today_interview}")
print(f"  Organized: {today_organized}")
print(f"  Spam deleted: {today_spam}")
print()

# Check all runs
all_runs = db.query(ProcessRun).all()
print(f"All runs in database: {len(all_runs)}")
for run in all_runs:
    print(f"  Run {run.id}: {run.run_timestamp} - {run.total_emails} emails")
