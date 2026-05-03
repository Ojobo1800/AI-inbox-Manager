"""
Email fetching execution script.

This script connects to an email inbox via IMAP, fetches emails,
and converts them to the format expected by the classification system.

Design principles:
- Pure logic separated from I/O for testability
- Deterministic email parsing
- Comprehensive error handling
- Safe connection management
"""

import email
from email.message import Message
import imaplib
import logging
import os
import json
from datetime import datetime
from email.header import decode_header
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailFetchError(Exception):
    """Raised when email fetching fails."""
    pass


class EmailConnectionError(Exception):
    """Raised when connection to email server fails."""
    pass


def delete_emails(
    server: str,
    port: int,
    email_address: str,
    password: str,
    email_ids: List[str],
    folder: str = "INBOX"
) -> int:
    """
    Delete emails from the server.

    Args:
        server: IMAP server address
        port: IMAP port
        email_address: Email address
        password: Email password
        email_ids: List of email IDs to delete
        folder: Folder to delete from

    Returns:
        Number of emails successfully deleted
    """
    if not email_ids:
        return 0

    try:
        # Connect
        imap = connect_to_imap(server, port, email_address, password)

        # Select folder (writable - not readonly)
        imap.select(folder)

        deleted_count = 0
        for email_id in email_ids:
            try:
                # Mark for deletion
                imap.store(email_id, '+FLAGS', '\\Deleted')
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to mark email {email_id} for deletion: {e}")

        # Expunge (permanently delete marked emails)
        imap.expunge()

        logger.info(f"Successfully deleted {deleted_count} email(s)")

        # Close connection
        imap.logout()

        return deleted_count

    except Exception as e:
        logger.error(f"Email deletion failed: {e}")
        raise EmailFetchError(f"Failed to delete emails: {str(e)}")


def move_emails(
    server: str,
    port: int,
    email_address: str,
    password: str,
    email_moves: Dict[str, str],
    source_folder: str = "INBOX"
) -> int:
    """
    Move emails to different folders on the server.

    Args:
        server: IMAP server address
        port: IMAP port
        email_address: Email address
        password: Email password
        email_moves: Dictionary mapping email_id -> destination_folder
        source_folder: Source folder (default: INBOX)

    Returns:
        Number of emails successfully moved
    """
    if not email_moves:
        return 0

    def _ensure_folder(imap_conn, folder: str) -> bool:
        """Create folder/label if it does not already exist. Returns True if ready."""
        quoted = f'"{folder}"'
        status, data = imap_conn.select(quoted)
        if status == "OK":
            return True
        # Folder missing — create it
        status, data = imap_conn.create(quoted)
        if status == "OK":
            logger.info(f"Created Gmail label/folder: {folder}")
            return True
        logger.warning(f"Could not create folder '{folder}': {data}")
        return False

    try:
        # Connect
        imap = connect_to_imap(server, port, email_address, password)

        # Pre-create all destination folders that don't exist yet
        needed_folders = set(email_moves.values())
        for folder in needed_folders:
            _ensure_folder(imap, folder)

        # Select source folder (writable)
        imap.select(source_folder)

        moved_count = 0
        for email_id, dest_folder in email_moves.items():
            try:
                # Quote folder name properly for IMAP
                quoted_folder = f'"{dest_folder}"'

                # Copy to destination folder
                imap.copy(email_id, quoted_folder)

                # Mark original for deletion
                imap.store(email_id, '+FLAGS', '\\Deleted')
                moved_count += 1
            except Exception as e:
                logger.error(f"Failed to move email {email_id} to {dest_folder}: {e}")

        # Expunge deleted emails
        imap.expunge()

        logger.info(f"Successfully moved {moved_count} email(s)")

        # Close connection
        imap.logout()

        return moved_count

    except Exception as e:
        logger.error(f"Email moving failed: {e}")
        raise EmailFetchError(f"Failed to move emails: {str(e)}")


def connect_to_imap(
    server: str,
    port: int,
    email_address: str,
    password: str,
    use_ssl: bool = True
) -> imaplib.IMAP4_SSL:
    """
    Connect to IMAP email server.

    Automatically uses OAuth2 (XOAUTH2) when config/gmail_token.json exists,
    falling back to password auth otherwise.

    Args:
        server: IMAP server address (e.g., imap.gmail.com)
        port: IMAP port (usually 993 for SSL)
        email_address: Email account address
        password: Account password or app-specific password (used if no OAuth2 token)
        use_ssl: Use SSL connection (recommended)

    Returns:
        Connected IMAP client

    Raises:
        EmailConnectionError: If connection or authentication fails
    """
    try:
        logger.info(f"Connecting to IMAP server: {server}:{port}")

        if use_ssl:
            imap = imaplib.IMAP4_SSL(server, port)
        else:
            imap = imaplib.IMAP4(server, port)

        # Use OAuth2 XOAUTH2 if token exists, else fall back to password
        token_path = Path(__file__).parent.parent / "config" / "gmail_token.json"
        if token_path.exists():
            try:
                from gmail_auth import get_access_token
                access_token = get_access_token()
                # XOAUTH2 string: "user=<email>\x01auth=Bearer <token>\x01\x01"
                auth_string = f"user={email_address}\x01auth=Bearer {access_token}\x01\x01"
                imap.authenticate("XOAUTH2", lambda _: auth_string.encode())
                logger.info(f"Authenticated via OAuth2 as: {email_address}")
            except Exception as oauth_err:
                logger.warning(f"OAuth2 failed, falling back to password: {oauth_err}")
                imap.login(email_address, password)
                logger.info(f"Authenticated via password as: {email_address}")
        else:
            logger.info(f"Authenticating via password as: {email_address}")
            imap.login(email_address, password)

        logger.info("Successfully connected and authenticated")
        return imap

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP authentication failed: {e}")
        raise EmailConnectionError(f"Authentication failed: {str(e)}")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        raise EmailConnectionError(f"Connection failed: {str(e)}")


def select_folder(imap: imaplib.IMAP4_SSL, folder: str = "INBOX") -> int:
    """
    Select email folder to read from.

    Args:
        imap: Connected IMAP client
        folder: Folder name (default: INBOX)

    Returns:
        Number of messages in folder

    Raises:
        EmailFetchError: If folder selection fails
    """
    try:
        logger.info(f"Selecting folder: {folder}")
        status, messages = imap.select(folder, readonly=True)

        if status != "OK":
            raise EmailFetchError(f"Failed to select folder: {folder}")

        message_count = int(messages[0])
        logger.info(f"Folder contains {message_count} messages")
        return message_count

    except Exception as e:
        logger.error(f"Folder selection failed: {e}")
        raise EmailFetchError(f"Failed to select folder: {str(e)}")


def search_emails(
    imap: imaplib.IMAP4_SSL,
    criteria: str = "UNSEEN",
    limit: Optional[int] = None
) -> List[str]:
    """
    Search for emails matching criteria.

    Args:
        imap: Connected IMAP client
        criteria: IMAP search criteria (e.g., "UNSEEN", "ALL")
        limit: Maximum number of emails to fetch (None = all)

    Returns:
        List of email IDs matching criteria

    Raises:
        EmailFetchError: If search fails
    """
    try:
        logger.info(f"Searching for emails with criteria: {criteria}")
        status, messages = imap.search(None, criteria)

        if status != "OK":
            raise EmailFetchError(f"Search failed with criteria: {criteria}")

        # Get list of email IDs
        email_ids = messages[0].split()

        if limit and len(email_ids) > limit:
            logger.info(f"Limiting results from {len(email_ids)} to {limit}")
            email_ids = email_ids[:limit]

        logger.info(f"Found {len(email_ids)} matching emails")
        return [email_id.decode() for email_id in email_ids]

    except Exception as e:
        logger.error(f"Email search failed: {e}")
        raise EmailFetchError(f"Search failed: {str(e)}")


def decode_email_header(header_value: str) -> str:
    """
    Decode email header that may be encoded.

    Args:
        header_value: Header value (potentially encoded)

    Returns:
        Decoded string
    """
    if not header_value:
        return ""

    try:
        decoded_parts = decode_header(header_value)
        decoded_string = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_string += str(part)

        return decoded_string.strip()
    except Exception as e:
        logger.warning(f"Failed to decode header '{header_value}': {e}")
        return str(header_value)


def extract_email_body(msg: Message) -> str:
    """
    Extract plain text body from email message.

    Args:
        msg: Parsed email message

    Returns:
        Email body as plain text
    """
    body = ""

    try:
        # Handle multipart emails
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                # Get plain text
                if content_type == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    break
                # Fallback to HTML if no plain text
                elif content_type == "text/html" and not body:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    # Simple HTML to text conversion (strip tags)
                    import re
                    body = re.sub('<[^<]+?>', '', html_body)
        else:
            # Single part message
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")

        return body.strip()

    except Exception as e:
        logger.warning(f"Failed to extract email body: {e}")
        return ""


def parse_email_message(raw_email: bytes, email_id: str) -> Dict[str, Any]:
    """
    Parse raw email into structured format.

    This is pure parsing logic - no I/O, easily testable.

    Args:
        raw_email: Raw email bytes from IMAP
        email_id: Unique email ID

    Returns:
        Dictionary with parsed email fields
    """
    try:
        # Parse email
        msg = email.message_from_bytes(raw_email)

        # Extract headers
        subject = decode_email_header(msg.get("Subject", ""))
        from_header = decode_email_header(msg.get("From", ""))
        date_header = msg.get("Date", "")

        # Parse sender email and name
        sender_email = ""
        sender_name = ""
        if from_header:
            # Format: "Name <email@example.com>" or "email@example.com"
            import re
            match = re.match(r'(.+?)\s*<(.+?)>', from_header)
            if match:
                sender_name = match.group(1).strip().strip('"')
                sender_email = match.group(2).strip()
            else:
                sender_email = from_header.strip()

        # Parse date
        email_date = ""
        if date_header:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_header)
                email_date = dt.isoformat()
            except Exception as e:
                logger.warning(f"Failed to parse date '{date_header}': {e}")
                email_date = date_header

        # Extract body
        body_content = extract_email_body(msg)

        return {
            "subject": subject,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "email_date": email_date,
            "body_content": body_content,
            "email_id": email_id,
            "message_id": msg.get("Message-ID", ""),
        }

    except Exception as e:
        logger.error(f"Failed to parse email {email_id}: {e}")
        raise EmailFetchError(f"Email parsing failed: {str(e)}")


def fetch_email_by_id(imap: imaplib.IMAP4_SSL, email_id: str) -> bytes:
    """
    Fetch raw email content by ID.

    Args:
        imap: Connected IMAP client
        email_id: Email ID to fetch

    Returns:
        Raw email bytes

    Raises:
        EmailFetchError: If fetch fails
    """
    try:
        status, msg_data = imap.fetch(email_id.encode(), "(RFC822)")

        if status != "OK":
            raise EmailFetchError(f"Failed to fetch email {email_id}")

        raw_email = msg_data[0][1]
        return raw_email

    except Exception as e:
        logger.error(f"Failed to fetch email {email_id}: {e}")
        raise EmailFetchError(f"Fetch failed: {str(e)}")


def fetch_emails(
    server: str,
    port: int,
    email_address: str,
    password: str,
    folder: str = "INBOX",
    criteria: str = "UNSEEN",
    limit: Optional[int] = None,
    mark_as_read: bool = False
) -> List[Dict[str, Any]]:
    """
    Main function to fetch and parse emails from inbox.

    Args:
        server: IMAP server address
        port: IMAP port
        email_address: Email account address
        password: Account password
        folder: Folder to fetch from (default: INBOX)
        criteria: Search criteria (default: UNSEEN)
        limit: Maximum emails to fetch (None = all)
        mark_as_read: Mark emails as read after fetching

    Returns:
        List of parsed email dictionaries

    Raises:
        EmailConnectionError: If connection fails
        EmailFetchError: If fetching/parsing fails
    """
    imap = None
    try:
        # Connect to server
        imap = connect_to_imap(server, port, email_address, password)

        # Select folder
        select_folder(imap, folder)

        # Search for emails
        email_ids = search_emails(imap, criteria, limit)

        if not email_ids:
            logger.info("No emails found matching criteria")
            return []

        # Fetch and parse each email
        emails = []
        for email_id in email_ids:
            try:
                logger.info(f"Fetching email {email_id}")
                raw_email = fetch_email_by_id(imap, email_id)
                parsed_email = parse_email_message(raw_email, email_id)
                emails.append(parsed_email)

                # Mark as read if requested
                if mark_as_read:
                    imap.store(email_id.encode(), '+FLAGS', '\\Seen')
                    logger.info(f"Marked email {email_id} as read")

            except EmailFetchError as e:
                logger.error(f"Skipping email {email_id}: {e}")
                continue

        logger.info(f"Successfully fetched {len(emails)} emails")
        return emails

    finally:
        # Always close connection
        if imap:
            try:
                imap.close()
                imap.logout()
                logger.info("IMAP connection closed")
            except:
                pass


def save_emails_to_file(emails: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Save fetched emails to JSON file.

    Args:
        emails: List of parsed email dictionaries
        output_path: Path to save JSON file
    """
    logger.info(f"Saving {len(emails)} emails to {output_path}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(emails, f, indent=2, ensure_ascii=False)

    logger.info("Emails saved successfully")


def main() -> None:
    """
    CLI entry point for email fetching.

    Usage:
        python fetch_emails.py <output_file> [--mark-read] [--limit N]
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fetch_emails.py <output_file> [--mark-read] [--limit N]")
        print("\nFetches emails from configured inbox and saves to JSON file.")
        print("\nOptions:")
        print("  --mark-read    Mark fetched emails as read")
        print("  --limit N      Fetch maximum N emails")
        sys.exit(1)

    output_file = Path(sys.argv[1])
    mark_as_read = "--mark-read" in sys.argv

    # Parse limit
    limit = None
    if "--limit" in sys.argv:
        try:
            limit_index = sys.argv.index("--limit")
            limit = int(sys.argv[limit_index + 1])
        except (IndexError, ValueError):
            print("Error: --limit requires a number")
            sys.exit(1)

    # Load configuration from environment
    server = os.getenv("EMAIL_SERVER")
    port = int(os.getenv("EMAIL_PORT", "993"))
    email_address = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    folder = os.getenv("EMAIL_FOLDER", "INBOX")
    criteria = os.getenv("EMAIL_SEARCH_CRITERIA", "UNSEEN")

    if not all([server, email_address, password]):
        print("Error: Missing required environment variables:")
        print("  EMAIL_SERVER")
        print("  EMAIL_ADDRESS")
        print("  EMAIL_PASSWORD")
        print("\nSet these in your .env file")
        sys.exit(1)

    try:
        # Fetch emails
        print(f"\nFetching emails from {email_address}...")
        print(f"Server: {server}:{port}")
        print(f"Folder: {folder}")
        print(f"Criteria: {criteria}")
        if limit:
            print(f"Limit: {limit} emails")

        emails = fetch_emails(
            server=server,
            port=port,
            email_address=email_address,
            password=password,
            folder=folder,
            criteria=criteria,
            limit=limit,
            mark_as_read=mark_as_read
        )

        # Save to file
        save_emails_to_file(emails, output_file)

        # Report results
        print(f"\nFetch complete:")
        print(f"  Emails fetched: {len(emails)}")
        print(f"  Saved to: {output_file}")
        if mark_as_read:
            print(f"  Marked as read: Yes")

        sys.exit(0)

    except EmailConnectionError as e:
        logger.error(f"Connection failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        print("\nCheck your email credentials and server settings")
        sys.exit(2)

    except EmailFetchError as e:
        logger.error(f"Fetch failed: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(2)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
