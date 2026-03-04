"""
Explore email folders on the IMAP server.

This script connects to the email server and lists all available folders,
helping us understand the existing folder structure for interview emails.
"""

import os
import imaplib
from dotenv import load_dotenv

# Load environment
load_dotenv()

def list_email_folders():
    """List all available folders on the IMAP server."""
    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")

    print(f"Connecting to {server}:{port}...")
    imap = imaplib.IMAP4_SSL(server, port)

    print(f"Authenticating as {email_address}...")
    imap.login(email_address, password)

    print("\nAvailable folders:\n")
    print("=" * 60)

    # List all folders
    status, folders = imap.list()

    if status == 'OK':
        for folder in folders:
            # Decode folder name
            folder_str = folder.decode('utf-8')
            print(folder_str)

    print("=" * 60)

    imap.logout()
    print("\nConnection closed.")


if __name__ == "__main__":
    list_email_folders()
