"""
Fetch sample emails from interview folders to understand patterns.

This helps us improve the classification system by studying real examples.
"""

import os
import sys
from pathlib import Path
from fetch_emails import fetch_emails

# Folders to sample
INTERVIEW_FOLDERS = [
    "Interview Request",
    "Interview Confirmation",
    "Interview Scheduling",
    "Interview Reschedule",
    "Interview Cancellation",
    "Interview Cancelled",
    "Interview Feedback",
    "Interview Rejection",
    "Interview Offer",
    "Final Interview Scheduled",
    "Phone Screen (HR or Recruiter)"
]


def main():
    """Fetch samples from each interview folder."""
    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    output_dir = Path("tmp/interview_samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    for folder in INTERVIEW_FOLDERS:
        print(f"\n{'='*60}")
        print(f"Sampling from: {folder}")
        print('='*60)

        try:
            # Fetch up to 3 emails from each folder
            emails = fetch_emails(
                server=server,
                port=port,
                email_address=email_address,
                password=password,
                folder=folder,
                criteria="ALL",  # Get any emails
                limit=3,
                mark_as_read=False
            )

            if emails:
                print(f"  Found {len(emails)} emails")
                for email in emails:
                    print(f"    - {email.get('subject', 'No Subject')[:60]}")

                # Save samples
                folder_safe = folder.replace(" ", "_").replace("(", "").replace(")", "")
                folder_dir = output_dir / folder_safe
                folder_dir.mkdir(exist_ok=True)

                import json
                for idx, email in enumerate(emails, 1):
                    filepath = folder_dir / f"sample_{idx}.json"
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(email, f, indent=2, ensure_ascii=False)

                print(f"  Saved to: {folder_dir}")
            else:
                print(f"  No emails found in this folder")

        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
