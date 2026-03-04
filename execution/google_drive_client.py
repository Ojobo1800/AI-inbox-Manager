"""
Google Drive API client for student data retrieval.

Connects to Google Drive using a service account to read student folders
and spreadsheets. Each student has a folder in the shared Drive containing
a spreadsheet with their details and a resume.

Design principles:
- Pure API wrapper with no business logic
- In-memory caching with configurable TTL
- Read-only access (never modifies Drive data)
- Testable with mocked Google API client
"""

import logging
import os
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default cache TTL in seconds (4 hours)
DEFAULT_CACHE_TTL_SECONDS = 4 * 60 * 60


class StudentCache:
    """Simple in-memory cache with TTL for student data."""

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl_seconds
        self._folder_list_cache: Optional[List[Dict[str, str]]] = None
        self._folder_list_timestamp: float = 0

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached value if not expired."""
        if key in self._cache:
            if time.time() - self._timestamps[key] < self._ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Cache a value with current timestamp."""
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def get_folder_list(self) -> Optional[List[Dict[str, str]]]:
        """Get cached folder list if not expired."""
        if self._folder_list_cache is not None:
            if time.time() - self._folder_list_timestamp < self._ttl:
                return self._folder_list_cache
            else:
                self._folder_list_cache = None
        return None

    def set_folder_list(self, folders: List[Dict[str, str]]) -> None:
        """Cache the folder list."""
        self._folder_list_cache = folders
        self._folder_list_timestamp = time.time()

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._timestamps.clear()
        self._folder_list_cache = None
        self._folder_list_timestamp = 0


class GoogleDriveClient:
    """
    Google Drive API client for reading student data.

    Requires a Google Cloud service account with read access to the
    shared student folder.
    """

    def __init__(
        self,
        service_account_key_path: Optional[str] = None,
        students_folder_id: Optional[str] = None,
        cache_ttl_hours: Optional[float] = None,
    ):
        """
        Initialize the Google Drive client.

        Args:
            service_account_key_path: Path to service account JSON key file.
                Defaults to GOOGLE_SERVICE_ACCOUNT_KEY_PATH env var.
            students_folder_id: ID of the shared students folder in Drive.
                Defaults to GOOGLE_DRIVE_STUDENTS_FOLDER_ID env var.
            cache_ttl_hours: Cache TTL in hours.
                Defaults to STUDENT_CACHE_TTL_HOURS env var or 4 hours.
        """
        self._key_path = service_account_key_path or os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_KEY_PATH"
        )
        self._folder_id = students_folder_id or os.getenv(
            "GOOGLE_DRIVE_STUDENTS_FOLDER_ID"
        )

        ttl_hours = cache_ttl_hours or float(
            os.getenv("STUDENT_CACHE_TTL_HOURS", "4")
        )
        self._cache = StudentCache(ttl_seconds=int(ttl_hours * 3600))

        self._drive_service = None
        self._sheets_service = None

    def _get_drive_service(self):
        """
        Lazily initialize the Google Drive API service.

        Returns:
            Google Drive API service object

        Raises:
            RuntimeError: If credentials or libraries are missing
        """
        if self._drive_service is not None:
            return self._drive_service

        if not self._key_path:
            raise ValueError(
                "GOOGLE_SERVICE_ACCOUNT_KEY_PATH not configured. "
                "Set environment variable or pass service_account_key_path."
            )

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "Google API libraries not installed. Install with: "
                "pip install google-api-python-client google-auth"
            )

        try:
            credentials = service_account.Credentials.from_service_account_file(
                self._key_path,
                scopes=[
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/spreadsheets.readonly",
                ],
            )
            self._drive_service = build("drive", "v3", credentials=credentials)
            self._sheets_service = build("sheets", "v4", credentials=credentials)
            logger.info("Google Drive API client initialized successfully")
            return self._drive_service
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Drive API: {e}")

    def _get_sheets_service(self):
        """Get the Google Sheets API service (initializes Drive service if needed)."""
        if self._sheets_service is None:
            self._get_drive_service()
        return self._sheets_service

    def list_student_folders(
        self, parent_folder_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        List all student folders in the shared Drive folder.

        Args:
            parent_folder_id: ID of parent folder. Defaults to configured folder.

        Returns:
            List of dicts with 'id', 'name' for each student folder

        Raises:
            RuntimeError: If API call fails
        """
        folder_id = parent_folder_id or self._folder_id
        if not folder_id:
            raise ValueError(
                "No students folder ID configured. "
                "Set GOOGLE_DRIVE_STUDENTS_FOLDER_ID or pass parent_folder_id."
            )

        # Check cache
        cached = self._cache.get_folder_list()
        if cached is not None:
            logger.info(f"Returning {len(cached)} cached student folders")
            return cached

        try:
            service = self._get_drive_service()
            folders = []
            page_token = None

            while True:
                response = (
                    service.files()
                    .list(
                        q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                        fields="nextPageToken, files(id, name)",
                        pageToken=page_token,
                        pageSize=100,
                    )
                    .execute()
                )

                for item in response.get("files", []):
                    folders.append({"id": item["id"], "name": item["name"]})

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            self._cache.set_folder_list(folders)
            logger.info(f"Listed {len(folders)} student folders from Drive")
            return folders

        except Exception as e:
            logger.error(f"Failed to list student folders: {e}")
            raise RuntimeError(f"Failed to list student folders: {e}")

    def find_student_folder(
        self, username: str, parent_folder_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Find a student's folder by matching username to folder name.

        Args:
            username: Student username (e.g., "john.doe" from john.doe@gmail.com)
            parent_folder_id: Optional parent folder ID override

        Returns:
            Dict with 'id' and 'name' if found, None otherwise
        """
        folders = self.list_student_folders(parent_folder_id)
        username_lower = username.lower()

        for folder in folders:
            if folder["name"].lower() == username_lower:
                logger.info(
                    f"Found student folder: {folder['name']} (id: {folder['id']})"
                )
                return folder

        # Try partial match (folder name contains the username)
        for folder in folders:
            if username_lower in folder["name"].lower():
                logger.info(
                    f"Found student folder via partial match: {folder['name']}"
                )
                return folder

        logger.warning(f"No folder found for student username: {username}")
        return None

    def find_spreadsheet_in_folder(
        self, folder_id: str
    ) -> Optional[Dict[str, str]]:
        """
        Find the spreadsheet file inside a student's folder.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            Dict with 'id' and 'name' of the spreadsheet, None if not found
        """
        try:
            service = self._get_drive_service()
            response = (
                service.files()
                .list(
                    q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                    fields="files(id, name)",
                    pageSize=10,
                )
                .execute()
            )

            files = response.get("files", [])
            if files:
                spreadsheet = {
                    "id": files[0]["id"],
                    "name": files[0]["name"],
                }
                logger.info(
                    f"Found spreadsheet: {spreadsheet['name']} (id: {spreadsheet['id']})"
                )
                return spreadsheet

            logger.warning(f"No spreadsheet found in folder: {folder_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to find spreadsheet in folder {folder_id}: {e}")
            raise RuntimeError(f"Failed to find spreadsheet: {e}")

    def read_spreadsheet(
        self, spreadsheet_id: str, range_name: str = "Sheet1"
    ) -> List[List[str]]:
        """
        Read data from a Google Spreadsheet.

        Args:
            spreadsheet_id: Google Spreadsheet ID
            range_name: Sheet name or A1 notation range

        Returns:
            List of rows, where each row is a list of cell values
        """
        try:
            service = self._get_sheets_service()
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute()
            )

            values = result.get("values", [])
            logger.info(
                f"Read {len(values)} rows from spreadsheet {spreadsheet_id}"
            )
            return values

        except Exception as e:
            logger.error(f"Failed to read spreadsheet {spreadsheet_id}: {e}")
            raise RuntimeError(f"Failed to read spreadsheet: {e}")

    def read_student_spreadsheet(
        self, folder_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find and read the spreadsheet inside a student's folder.

        Returns the data as a dictionary with headers as keys.

        Args:
            folder_id: Student's Google Drive folder ID

        Returns:
            Dict with spreadsheet data (header → value mapping), None if not found
        """
        spreadsheet = self.find_spreadsheet_in_folder(folder_id)
        if not spreadsheet:
            return None

        rows = self.read_spreadsheet(spreadsheet["id"])
        if not rows or len(rows) < 2:
            logger.warning("Spreadsheet has insufficient data (need header + data rows)")
            return None

        # Parse as key-value pairs
        # Supports two formats:
        # 1. Two-column layout: Column A = field name, Column B = value
        # 2. Header row layout: Row 1 = headers, Row 2+ = values

        data = {}

        # Check if it's a two-column key-value format
        if len(rows[0]) == 2:
            for row in rows:
                if len(row) >= 2:
                    key = str(row[0]).strip().lower().replace(" ", "_")
                    value = str(row[1]).strip() if row[1] else None
                    if key:
                        data[key] = value
        else:
            # Header row format
            headers = [str(h).strip().lower().replace(" ", "_") for h in rows[0]]
            if len(rows) > 1:
                values = rows[1]
                for i, header in enumerate(headers):
                    if header and i < len(values):
                        data[header] = str(values[i]).strip() if values[i] else None
                    elif header:
                        data[header] = None

        data["_spreadsheet_id"] = spreadsheet["id"]
        data["_spreadsheet_name"] = spreadsheet["name"]

        logger.info(f"Parsed student spreadsheet with {len(data)} fields")
        return data

    def get_student_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Full lookup: find student folder → read spreadsheet → return structured data.

        Results are cached by username for the configured TTL.

        Args:
            username: Student username (local part of their Gmail)

        Returns:
            Dict with student info from their spreadsheet, None if not found
        """
        # Check cache
        cached = self._cache.get(username)
        if cached is not None:
            logger.info(f"Returning cached student info for: {username}")
            return cached

        # Find folder
        folder = self.find_student_folder(username)
        if not folder:
            logger.warning(f"No folder found for student: {username}")
            return None

        # Read spreadsheet
        student_data = self.read_student_spreadsheet(folder["id"])
        if not student_data:
            logger.warning(f"No spreadsheet data for student: {username}")
            return None

        # Add folder metadata
        student_data["_folder_id"] = folder["id"]
        student_data["_folder_name"] = folder["name"]
        student_data["_username"] = username

        # Cache the result
        self._cache.set(username, student_data)

        return student_data

    def clear_cache(self) -> None:
        """Clear all cached student data."""
        self._cache.clear()
        logger.info("Student data cache cleared")
