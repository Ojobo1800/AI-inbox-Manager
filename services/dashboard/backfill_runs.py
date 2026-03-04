"""Backfill ProcessRun records from existing summary.json files."""
import sys
from pathlib import Path

# Add api directory to path
api_dir = Path(__file__).parent / "api"
sys.path.insert(0, str(api_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import ProcessRun
from integration.process_runner import _import_latest_summary

# Create database session
engine = create_engine('sqlite:///email_dashboard.db')
Session = sessionmaker(bind=engine)
db = Session()

# Find project root (go up from services/dashboard to ClaudeTest)
project_root = Path(__file__).parent.parent.parent

print("Starting backfill of ProcessRun records...")
print(f"Project root: {project_root}")
print()

# Get all auto_process directories
tmp_dir = project_root / "tmp"
auto_process_dirs = sorted(tmp_dir.glob("auto_process_*"))

print(f"Found {len(auto_process_dirs)} auto_process directories")
print()

imported_count = 0
already_imported_count = 0
error_count = 0

for directory in auto_process_dirs:
    summary_file = directory / "summary.json"

    if not summary_file.exists():
        print(f"SKIP {directory.name}: No summary.json file")
        error_count += 1
        continue

    # Temporarily change the _import_latest_summary to import this specific directory
    # Instead, let's manually parse and import
    try:
        import json
        from datetime import datetime

        with open(summary_file, 'r') as f:
            summary = json.load(f)

        # Handle both formats
        if 'statistics' in summary:
            stats = summary['statistics']
            run_timestamp = datetime.fromisoformat(summary['processing_timestamp'].replace('Z', '+00:00'))
            total_emails = stats['total_emails']
            categories = stats.get('categories', {})
            interview_count = stats.get('interview_requests', 0)
            organized = stats.get('organized', 0)
            spam_deleted = stats.get('spam_deleted', 0)
        else:
            run_timestamp = datetime.fromisoformat(summary['run_timestamp'])
            total_emails = summary['total_emails']
            categories = summary.get('categories', {})
            interview_count = summary.get('categories', {}).get('Interview Request', 0)
            organized = sum(
                count for cat, count in categories.items()
                if cat not in ['Interview Request', 'Spam or Scam', 'Keep in Inbox']
            )
            spam_deleted = categories.get('Spam or Scam', 0)

        # Check if already imported
        existing = db.query(ProcessRun).filter(
            ProcessRun.run_timestamp == run_timestamp
        ).first()

        if existing:
            print(f"ALREADY {directory.name}: Already imported (ID: {existing.id})")
            already_imported_count += 1
            continue

        # Create new process run
        process_run = ProcessRun(
            run_timestamp=run_timestamp,
            total_emails=total_emails,
            interview_requests=interview_count,
            organized=organized,
            spam_deleted=spam_deleted,
            categories_breakdown=categories,
            duration_seconds=0,
            status='success',
            error_log=None
        )

        db.add(process_run)
        db.commit()

        print(f"IMPORTED {directory.name}: (ID: {process_run.id}, {total_emails} emails, {interview_count} interviews)")
        imported_count += 1

    except Exception as e:
        print(f"ERROR {directory.name}: {str(e)}")
        error_count += 1
        db.rollback()

print()
print("=" * 60)
print(f"Backfill complete!")
print(f"  Newly imported: {imported_count}")
print(f"  Already imported: {already_imported_count}")
print(f"  Errors: {error_count}")
print(f"  Total: {len(auto_process_dirs)}")
print("=" * 60)

db.close()
