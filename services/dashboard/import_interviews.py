"""Import interview request emails from summary files into dashboard database."""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add paths
# From services/dashboard, go up 2 levels to ClaudeTest
project_root = Path(__file__).parent.parent.parent
api_dir = Path(__file__).parent / "api"
execution_dir = project_root / "execution"

sys.path.insert(0, str(api_dir))
sys.path.insert(0, str(execution_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Email, Classification
import imaplib
import email as email_lib
from email.header import decode_header

# Create database session
engine = create_engine('sqlite:///email_dashboard.db')
Session = sessionmaker(bind=engine)
db = Session()

print("Importing interview requests into database...")
print()

# Load environment from project root
from dotenv import load_dotenv
import os

# Load from project root .env (not dashboard .env)
env_file = project_root / ".env"
load_dotenv(env_file, override=True)

# Connect to IMAP
print(f"Connecting to {os.getenv('EMAIL_SERVER')}...")
try:
    mail = imaplib.IMAP4_SSL(os.getenv('EMAIL_SERVER'), int(os.getenv('EMAIL_PORT', 993)))
    mail.login(os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD'))
    mail.select('INBOX')
    print("Connected successfully")
    print()
except Exception as e:
    print(f"Error connecting to IMAP: {e}")
    sys.exit(1)

# Find all summary files with interview requests
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
        timestamp = interview['timestamp']

        total_found += 1

        # Check if already imported
        existing = db.query(Email).filter(Email.subject == subject).first()
        if existing:
            print(f"  SKIP: {subject[:60]}... (already imported)")
            total_skipped += 1
            continue

        # Search for email in IMAP
        try:
            # Search by subject
            search_query = f'(SUBJECT "{subject[:50]}")'  # Limit subject length for IMAP
            typ, data = mail.search(None, search_query)

            if not data[0]:
                print(f"  NOT FOUND in IMAP: {subject[:60]}...")
                continue

            # Get the first matching email
            email_ids = data[0].split()
            if not email_ids:
                continue

            email_id = email_ids[0].decode()

            # Fetch email details
            typ, msg_data = mail.fetch(email_id, '(RFC822)')

            if not msg_data or not msg_data[0]:
                continue

            email_message = email_lib.message_from_bytes(msg_data[0][1])

            # Get from address
            from_addr = email_message.get('From', '')

            # Get date
            date_str = email_message.get('Date', '')
            try:
                received_date = email_lib.utils.parsedate_to_datetime(date_str)
            except:
                received_date = datetime.utcnow()

            # Get body
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')

            # Create Email record
            email_record = Email(
                email_id=email_id,
                subject=subject,
                from_address=from_addr,
                received_date=received_date,
                body_preview=body[:500] if body else "",
                full_body=body,
                current_folder="INBOX",
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
                position=None,  # Not in summary
                classification_timestamp=datetime.fromisoformat(timestamp.replace('Z', '+00:00')),
                classifier_version="gpt-4o-2024-08-06",
                raw_response=json.dumps(interview)
            )

            db.add(classification)
            db.commit()

            print(f"  IMPORTED: {subject[:60]}... (confidence: {confidence})")
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

# Close connections
mail.logout()
db.close()
