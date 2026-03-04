"""Check ProcessRun records in database."""
from sqlalchemy import create_engine, text

engine = create_engine('sqlite:///email_dashboard.db')

with engine.connect() as conn:
    # Check ProcessRuns
    result = conn.execute(text('SELECT id, run_timestamp, total_emails, interview_requests, organized, spam_deleted FROM process_runs ORDER BY run_timestamp DESC LIMIT 5'))
    rows = result.fetchall()

    print(f'Found {len(rows)} ProcessRun records:')
    for r in rows:
        print(f'  ID: {r[0]}, Timestamp: {r[1]}, Total: {r[2]}, Interviews: {r[3]}, Organized: {r[4]}, Spam: {r[5]}')

    print()

    # Check total count
    result = conn.execute(text('SELECT COUNT(*) FROM process_runs'))
    total = result.scalar()
    print(f'Total ProcessRun records: {total}')
