import gspread
from google.oauth2 import service_account

from app.core.config import settings


SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_HEADERS = [
    "record_key",
    "email_address",
    "company_name",
    "position_title",
    "interview_type",
    "interview_datetime",
    "status",
    "source",
    "source_message_id",
    "subject",
    "sender",
    "snippet",
    "received_at",
]


def get_gspread_client() -> gspread.Client:
    creds = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json,
        scopes=SHEETS_SCOPES,
    )
    if settings.google_workspace_user:
        creds = creds.with_subject(settings.google_workspace_user)
    return gspread.authorize(creds)


def _get_or_create_worksheet(spreadsheet, title: str):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=30)
        ws.append_row(SHEET_HEADERS, value_input_option="RAW")
        return ws


def append_interview_record(record: dict) -> None:
    if not settings.google_sheet_id:
        raise ValueError("GOOGLE_SHEET_ID is required")

    worksheet_name = settings.google_sheet_worksheet or "InterviewTracker"
    client = get_gspread_client()
    spreadsheet = client.open_by_key(settings.google_sheet_id)
    worksheet = _get_or_create_worksheet(spreadsheet, worksheet_name)

    row = [record.get(col, "") for col in SHEET_HEADERS]
    worksheet.append_row(row, value_input_option="RAW")
