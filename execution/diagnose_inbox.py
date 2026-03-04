"""
Diagnostic script to show current inbox state and classify emails.

This helps debug why emails are disappearing.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fetch_emails import fetch_emails
from classify_email import classify_email
from process_inbox_auto import is_genuine_interview_request

load_dotenv()

def diagnose_inbox():
    """Show all emails in inbox with their classification."""

    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    print("\n" + "="*70)
    print("INBOX DIAGNOSTIC - CURRENT STATE")
    print("="*70)

    # Fetch ALL emails (both read and unread)
    print("\nFetching ALL emails from inbox...")
    all_emails = fetch_emails(
        server=server,
        port=port,
        email_address=email_address,
        password=password,
        folder="INBOX",
        criteria="ALL",
        mark_as_read=False
    )

    print(f"Found {len(all_emails)} total emails in inbox\n")

    # Fetch UNSEEN emails
    unseen_emails = fetch_emails(
        server=server,
        port=port,
        email_address=email_address,
        password=password,
        folder="INBOX",
        criteria="UNSEEN",
        mark_as_read=False
    )

    print(f"Found {len(unseen_emails)} UNREAD emails\n")
    unseen_ids = {e.get("email_id") for e in unseen_emails}

    # Show each email with classification
    print("="*70)
    print("EMAIL DETAILS & CLASSIFICATION")
    print("="*70 + "\n")

    for idx, email in enumerate(all_emails, 1):
        email_id = email.get("email_id")
        subject = email.get("subject", "No Subject")
        from_addr = email.get("from", "Unknown")
        is_unread = email_id in unseen_ids

        print(f"[{idx}] {'[UNREAD]' if is_unread else '[READ]  '}")
        print(f"    Subject: {subject[:60]}")
        print(f"    From: {from_addr[:60]}")

        # Classify
        try:
            classification = classify_email(email, validate_only=False)
            category = classification.get("category")
            confidence = classification.get("confidence", 0)
            company = classification.get("extracted_data", {}).get("company_name", "N/A")

            is_genuine = is_genuine_interview_request(classification)

            print(f"    Category: {category}")
            print(f"    Confidence: {confidence:.0%}")
            print(f"    Company: {company}")
            print(f"    Genuine Interview Request: {'YES' if is_genuine else 'NO'}")

            if is_genuine:
                print(f"    >>> WOULD KEEP IN INBOX <<<")
            elif category == "Other":
                print(f"    >>> WOULD DELETE (SPAM) <<<")
            else:
                print(f"    >>> WOULD MOVE TO FOLDER <<<")

        except Exception as e:
            print(f"    ERROR classifying: {e}")

        print()

    print("="*70)
    print("DIAGNOSTIC COMPLETE")
    print("="*70)


if __name__ == "__main__":
    diagnose_inbox()
