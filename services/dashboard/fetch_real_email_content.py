"""Fetch real email content from IMAP for existing interview records."""
import sys
import os
from pathlib import Path

# Add paths
project_root = Path(__file__).parent.parent.parent
api_dir = Path(__file__).parent / "api"
sys.path.insert(0, str(api_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Email, Classification
from dotenv import load_dotenv
import imaplib
import email as email_lib

# Load environment from project root
env_file = project_root / ".env"
load_dotenv(env_file, override=True)

# Create database session
engine = create_engine('sqlite:///email_dashboard.db')
Session = sessionmaker(bind=engine)
db = Session()

print("Fetching real email content from IMAP...")
print()

# Connect to IMAP
print(f"Connecting to {os.getenv('EMAIL_SERVER')}...")
try:
    mail = imaplib.IMAP4_SSL(os.getenv('EMAIL_SERVER'), int(os.getenv('EMAIL_PORT', 993)))
    mail.login(os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD'))

    # Get all folders
    typ, folders = mail.list()
    folder_names = []
    for folder in folders:
        # Parse folder name from response
        parts = folder.decode().split('"')
        if len(parts) >= 3:
            folder_names.append(parts[-2])

    print(f"Connected successfully. Found {len(folder_names)} folders:")
    print(f"  {', '.join(folder_names[:5])}...")
    print()
except Exception as e:
    print(f"Error connecting to IMAP: {e}")
    sys.exit(1)

# Get all interview request emails
interviews = db.query(Email, Classification).join(
    Classification, Email.id == Classification.email_id
).filter(
    Classification.category == "Interview Request"
).all()

print(f"Found {len(interviews)} interview request emails to fetch")
print()

total_processed = 0
total_updated = 0
total_not_found = 0

for email, classification in interviews:
    print(f"Processing: {email.subject[:60]}...")

    # Skip if already has real content
    if email.full_body and "[Interview request detected from automated processing]" not in email.full_body:
        print(f"  SKIP: Already has real content")
        continue

    try:
        # Search across all folders
        email_id = None
        found_folder = None

        for folder_name in folder_names:
            try:
                mail.select(f'"{folder_name}"')

                # Search for email in this folder by subject
                # Use quotes and escape special chars
                search_subject = email.subject.replace('"', '\\"')[:80]
                search_query = f'(SUBJECT "{search_subject}")'

                typ, data = mail.search(None, search_query)

                if data[0]:
                    email_ids = data[0].split()
                    if email_ids:
                        email_id = email_ids[0].decode()
                        found_folder = folder_name
                        break
            except:
                continue

        if not email_id:
            print(f"  NOT FOUND in any folder")
            total_not_found += 1
            total_processed += 1
            continue

        print(f"  Found in folder: {found_folder}")

        # Fetch full email
        typ, msg_data = mail.fetch(email_id, '(RFC822)')

        if not msg_data or not msg_data[0]:
            print(f"  ERROR: Could not fetch email content")
            total_processed += 1
            continue

        email_message = email_lib.message_from_bytes(msg_data[0][1])

        # Get from address
        from_addr = email_message.get('From', '')

        # Get date
        date_str = email_message.get('Date', '')
        try:
            received_date = email_lib.utils.parsedate_to_datetime(date_str)
        except:
            received_date = None

        # Get body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = ""

        if not body:
            print(f"  WARNING: No body content found")

        # Update Email record
        if from_addr:
            email.from_address = from_addr
        if received_date:
            email.received_date = received_date
        email.full_body = body
        email.body_preview = body[:500] if body else email.body_preview
        email.email_id = email_id

        db.commit()

        print(f"  UPDATED: Fetched {len(body)} chars from IMAP")
        total_updated += 1

    except Exception as e:
        print(f"  ERROR: {str(e)}")
        db.rollback()

    total_processed += 1

print()
print("=" * 60)
print(f"Fetch complete!")
print(f"  Total processed: {total_processed}")
print(f"  Successfully updated: {total_updated}")
print(f"  Not found in IMAP: {total_not_found}")
print("=" * 60)

# Close connections
mail.logout()
db.close()
