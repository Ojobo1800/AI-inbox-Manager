# Directive: Email Inbox Integration

## Goal
Connect to an email inbox, fetch job-related emails, and automatically classify them for downstream processing (logging, notifications, reporting).

## Context
This directive enables the email classification system to process real emails from a monitored inbox (Gmail, Outlook, or other IMAP-compatible service). Emails are fetched, classified, and marked as processed to prevent duplicate processing.

## Inputs
- **email_server**: IMAP server address (e.g., imap.gmail.com)
- **email_port**: IMAP port (usually 993 for SSL)
- **email_address**: Email account to monitor
- **email_password**: App-specific password or OAuth token
- **folder_name**: Inbox folder to monitor (default: "INBOX")
- **search_criteria**: Email filter criteria (e.g., UNSEEN, FROM specific sender)

## Outputs
- **fetched_emails**: List of email dictionaries with:
  - subject: Email subject line
  - sender_email: Sender email address
  - sender_name: Sender display name
  - email_date: Received timestamp
  - body_content: Email body (plain text)
  - email_id: IMAP message-sequence number — **NOT stable**. IMAP re-assigns it
    every session, so it must never be used as a database key or dedup key.
    Safe only for operations inside the same IMAP connection (fetch, move).
  - message_id: RFC 5322 `Message-ID` header — stable and globally unique.
    This is the key to use for de-duplication and database upserts.
  - raw_email: Full raw email for archival

## Steps

### 1. Connect to Email Server
- Use IMAP protocol to connect securely (SSL/TLS)
- Authenticate with provided credentials
- Handle connection failures gracefully
- Log connection attempts

### 2. Select Mailbox Folder
- Default to "INBOX" unless specified
- Support custom folder names (e.g., "Jobs", "Interviews")
- Verify folder exists

### 3. Search for Target Emails
- Default: Search for UNSEEN (unread) emails
- Optional filters:
  - Date range (emails from last N days)
  - Sender domain (e.g., FROM @company.com)
  - Subject keywords (e.g., SUBJECT "interview")
- Limit number of emails fetched per batch (default: 50)

### 4. Fetch and Parse Emails
- Download email headers and body
- Extract plain text from HTML if needed
- Parse sender information
- Decode special characters and encodings
- Extract attachments metadata (don't download yet)

### 5. Convert to Standard Format
- Transform to classification-compatible format:
  ```json
  {
    "subject": "...",
    "sender_email": "...",
    "sender_name": "...",
    "email_date": "ISO 8601",
    "body_content": "plain text",
    "email_id": "IMAP sequence number (ephemeral — same-session use only)",
    "message_id": "<...@host>  (RFC 5322 Message-ID — stable dedup key)"
  }
  ```

### 6. Mark as Processed (Optional)
- Mark as READ after successful fetch
- Move to processed folder
- Add custom label/flag
- **IMPORTANT**: Only mark after successful classification

## Edge Cases

### Connection Failures
- **Scenario**: Cannot connect to IMAP server (network, credentials, server down)
- **Handling**: Retry 3 times with exponential backoff, then fail gracefully and alert

### Authentication Errors
- **Scenario**: Invalid credentials or expired app password
- **Handling**: Do not retry (avoid account lockout), log error, alert administrator

### No New Emails
- **Scenario**: Search returns zero emails
- **Handling**: Return empty list, log info message, exit successfully (not an error)

### Malformed Emails
- **Scenario**: Email cannot be parsed (corrupted, unsupported encoding)
- **Handling**: Log warning with email ID, skip email, continue processing others

### Large Email Volume
- **Scenario**: More than batch limit (e.g., 1000+ unread emails)
- **Handling**: Process in batches, respect rate limits, add delays between batches

### HTML-Only Emails
- **Scenario**: Email has no plain text version, only HTML
- **Handling**: Extract text from HTML using html2text or similar, preserve links

### Duplicate Processing
- **Scenario**: Email already processed, or re-fetched on a later run
- **Handling**: De-duplicate on the RFC 5322 `Message-ID` header, never on the
  IMAP sequence number (`email_id`). The dashboard `emails` table has a UNIQUE
  index on `message_id`; `import_email_to_db()` upserts against it.
- **History**: From ~2026-06-29 to 2026-08-31 the importer keyed dedup on the
  IMAP sequence number. Because IMAP reuses those numbers every run, every new
  email collided with an old row and was silently dropped — the dashboard's
  email tables froze while Gmail sorting and Google Sheets kept working. Fixed
  by adding `emails.message_id` and keying on it.

## Safety Constraints

- **Never delete emails** - Only mark as read or move to folders
- **Never modify email content** - Preserve original for audit trail
- **Always use SSL/TLS** - No plaintext connections
- **Store credentials securely** - Use .env file, never hardcode
- **Rate limit requests** - Respect IMAP server limits (avoid IP bans)
- **Test in dev first** - Never connect to production inbox during development
- **Handle PII carefully** - Emails may contain sensitive personal information

## Email Provider Configuration

### Gmail
- Server: `imap.gmail.com`
- Port: `993`
- SSL: Required
- **App Password Required**: Enable 2FA, generate app-specific password
- Link: https://support.google.com/accounts/answer/185833

### Outlook/Microsoft 365
- Server: `outlook.office365.com`
- Port: `993`
- SSL: Required
- **Modern Auth**: May require OAuth2 instead of password

### Generic IMAP
- Server: Check provider documentation
- Port: Usually 993 (SSL) or 143 (STARTTLS)
- Test connection first

## Monitoring & Success Metrics

### Target Metrics
- **Fetch Success Rate**: >99% successful connections
- **Processing Time**: <5 seconds per email
- **Duplicate Rate**: <1% of emails processed twice
- **Error Rate**: <5% parsing/format errors

### Logging Requirements
- Log every connection attempt
- Log number of emails fetched per batch
- Track processing time per email
- Alert on authentication failures
- Alert on high error rates

## Related Scripts

- `execution/fetch_emails.py` - Main email fetching logic
- `execution/parse_email.py` - Email parsing and format conversion
- `execution/classify_email.py` - Classification (existing)
- `tests/execution/test_fetch_emails.py` - Unit tests

## Environment Variables

Required in `.env`:
```
# Email Configuration
EMAIL_SERVER=imap.gmail.com
EMAIL_PORT=993
EMAIL_ADDRESS=your-email@example.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_FOLDER=INBOX
EMAIL_BATCH_SIZE=50
EMAIL_MARK_AS_READ=false
```

## Testing Strategy

### Unit Tests
- Test IMAP connection with mock server
- Test email parsing with sample .eml files
- Test format conversion
- Test error handling

### Integration Tests
- Connect to test email account
- Fetch from test inbox
- Verify parsed format
- **Requires**: TEST_INTEGRATION=1 flag

### Manual Testing
- Send test emails to monitored inbox
- Verify fetching and classification
- Check marking/moving behavior

## Production Deployment Checklist

Before going live:
- [ ] App password generated (not regular password)
- [ ] Test connection successful
- [ ] Batch size configured appropriately
- [ ] Marking behavior confirmed (read/unread)
- [ ] Error alerts configured
- [ ] Logging working correctly
- [ ] Duplicate detection tested
- [ ] Rate limits understood and respected

## Revision History

- **v1.0** (2026-01-27): Initial email integration directive
- **v1.1** (2026-08-31): Documented that `email_id` is an ephemeral IMAP sequence
  number and must not be used as a database/dedup key. De-duplication now keys on
  the `Message-ID` header via the new `emails.message_id` column (UNIQUE). Root
  cause of the 2026-06-29 → 2026-08-31 dashboard-data freeze. See
  `execution/migrate_add_message_id.py` and
  `tests/execution/test_import_email_to_db.py`.
