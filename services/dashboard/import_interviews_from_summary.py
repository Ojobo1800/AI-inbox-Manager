"""Import interview request records from summary files (metadata only)."""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add paths
project_root = Path(__file__).parent.parent.parent
api_dir = Path(__file__).parent / "api"
sys.path.insert(0, str(api_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Email, Classification

# Create database session
engine = create_engine('sqlite:///email_dashboard.db')
Session = sessionmaker(bind=engine)
db = Session()

print("Importing interview requests from summaries...")
print()

# Find all summary files
tmp_dir = project_root / "tmp"
auto_process_dirs = sorted(tmp_dir.glob("auto_process_*"), reverse=True)

total_found = 0
total_imported = 0
total_skipped = 0

for directory in auto_process_dirs:
    summary_file = directory / "summary.json"

    if not summary_file.exists():
        continue

    with open(summary_file, 'r') as f:
        summary = json.load(f)

    interview_requests = summary.get('interview_requests', [])

    if not interview_requests:
        continue

    print(f"Processing {directory.name}: {len(interview_requests)} interviews")

    for interview in interview_requests:
        subject = interview['subject']
        company = interview.get('company')
        confidence = interview['confidence']
        timestamp_str = interview['timestamp']

        total_found += 1

        # Check if already imported (by subject + timestamp)
        classification_ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00').replace('+00:00', ''))

        existing_email = db.query(Email).filter(
            Email.subject == subject
        ).first()

        if existing_email:
            # Check if it has an interview request classification
            existing_class = db.query(Classification).filter(
                Classification.email_id == existing_email.id,
                Classification.category == "Interview Request"
            ).first()

            if existing_class:
                print(f"  SKIP: {subject[:60]}...")
                total_skipped += 1
                continue

        try:
            # Parse timestamp
            try:
                received_date = classification_ts
            except:
                received_date = datetime.utcnow()

            # Create Email record with placeholder data
            email_record = Email(
                email_id=f"summary_{directory.name}_{total_found}",  # Placeholder ID
                subject=subject,
                from_address="",  # Unknown
                received_date=received_date,
                body_preview="[Interview request detected from automated processing]",
                full_body="",
                current_folder="[Processed]",
                is_read=True,
                fetch_timestamp=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )

            db.add(email_record)
            db.flush()  # Get the ID

            # Create Classification record
            classification = Classification(
                email_id=email_record.id,
                category="Interview Request",
                confidence=confidence,
                company_name=company,
                position=None,
                classification_timestamp=received_date,
                classifier_version="gpt-4o-2024-08-06",
                raw_response=json.dumps(interview)
            )

            db.add(classification)
            db.commit()

            print(f"  IMPORTED: {subject[:60]}... ({company or 'Unknown'})")
            total_imported += 1

        except Exception as e:
            print(f"  ERROR: {subject[:60]}... - {str(e)}")
            db.rollback()

print()
print("=" * 60)
print(f"Import complete!")
print(f"  Total found in summaries: {total_found}")
print(f"  Successfully imported: {total_imported}")
print(f"  Skipped (already in DB): {total_skipped}")
print("=" * 60)

db.close()
