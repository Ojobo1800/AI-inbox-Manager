"""
Unit tests for google_drive_client.py

Tests the Google Drive API wrapper with mocked Google API client.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from execution.google_drive_client import (
    GoogleDriveClient,
    StudentCache,
)


class TestStudentCache:
    """Test the in-memory caching system."""

    def test_set_and_get(self):
        cache = StudentCache(ttl_seconds=3600)
        cache.set("user1", {"name": "Alice"})

        result = cache.get("user1")
        assert result == {"name": "Alice"}

    def test_get_missing_key(self):
        cache = StudentCache(ttl_seconds=3600)
        assert cache.get("missing") is None

    def test_expired_entry(self):
        cache = StudentCache(ttl_seconds=0)  # Immediate expiry
        cache.set("user1", {"name": "Alice"})
        # Cache with TTL=0 means any time check will expire it
        time.sleep(0.01)

        assert cache.get("user1") is None

    def test_folder_list_cache(self):
        cache = StudentCache(ttl_seconds=3600)
        folders = [{"id": "1", "name": "student1"}]
        cache.set_folder_list(folders)

        result = cache.get_folder_list()
        assert result == folders

    def test_folder_list_expired(self):
        cache = StudentCache(ttl_seconds=0)
        cache.set_folder_list([{"id": "1", "name": "student1"}])
        time.sleep(0.01)

        assert cache.get_folder_list() is None

    def test_clear(self):
        cache = StudentCache(ttl_seconds=3600)
        cache.set("user1", {"name": "Alice"})
        cache.set_folder_list([{"id": "1", "name": "student1"}])

        cache.clear()

        assert cache.get("user1") is None
        assert cache.get_folder_list() is None


class TestGoogleDriveClientInit:
    """Test client initialization."""

    def test_init_with_params(self):
        client = GoogleDriveClient(
            service_account_key_path="/path/to/key.json",
            students_folder_id="folder123",
            cache_ttl_hours=2,
        )
        assert client._key_path == "/path/to/key.json"
        assert client._folder_id == "folder123"

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "/env/key.json")
        monkeypatch.setenv("GOOGLE_DRIVE_STUDENTS_FOLDER_ID", "envfolder")
        monkeypatch.setenv("STUDENT_CACHE_TTL_HOURS", "6")

        client = GoogleDriveClient()
        assert client._key_path == "/env/key.json"
        assert client._folder_id == "envfolder"

    def test_missing_key_path_raises_on_service_init(self):
        client = GoogleDriveClient(
            service_account_key_path=None,
            students_folder_id="folder123",
        )
        # Won't fail until we try to use the service
        with pytest.raises(ValueError, match="GOOGLE_SERVICE_ACCOUNT_KEY_PATH"):
            client._get_drive_service()


class TestGoogleDriveClientFindFolder:
    """Test folder finding logic."""

    def test_find_exact_match(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )
        # Pre-populate cache to avoid API call
        client._cache.set_folder_list(
            [
                {"id": "folder1", "name": "john.doe"},
                {"id": "folder2", "name": "jane.smith"},
            ]
        )

        result = client.find_student_folder("john.doe")

        assert result is not None
        assert result["id"] == "folder1"
        assert result["name"] == "john.doe"

    def test_find_case_insensitive(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )
        client._cache.set_folder_list(
            [{"id": "folder1", "name": "John.Doe"}]
        )

        result = client.find_student_folder("john.doe")

        assert result is not None
        assert result["name"] == "John.Doe"

    def test_find_partial_match(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )
        client._cache.set_folder_list(
            [{"id": "folder1", "name": "john.doe - Data Analyst"}]
        )

        result = client.find_student_folder("john.doe")

        assert result is not None
        assert "john.doe" in result["name"].lower()

    def test_find_no_match(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )
        client._cache.set_folder_list(
            [{"id": "folder1", "name": "jane.smith"}]
        )

        result = client.find_student_folder("nonexistent.user")

        assert result is None


class TestGoogleDriveClientReadSpreadsheet:
    """Test spreadsheet reading and parsing."""

    def test_read_two_column_format(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )

        # Mock the sheets service
        mock_sheets = MagicMock()
        client._sheets_service = mock_sheets

        # Two-column key-value format
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["Full Name", "John Doe"],
                ["Personal Email", "john@personal.com"],
                ["Phone", "555-1234"],
                ["Assigned Gmail", "john.doe@gmail.com"],
            ]
        }

        # Mock find_spreadsheet to return a spreadsheet
        mock_drive = MagicMock()
        client._drive_service = mock_drive
        mock_drive.files().list().execute.return_value = {
            "files": [{"id": "sheet1", "name": "Student Info"}]
        }

        result = client.read_student_spreadsheet("folder1")

        assert result is not None
        assert result["full_name"] == "John Doe"
        assert result["personal_email"] == "john@personal.com"
        assert result["phone"] == "555-1234"

    def test_read_header_row_format(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )

        mock_sheets = MagicMock()
        client._sheets_service = mock_sheets

        # Header row format
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["Full Name", "Personal Email", "Phone", "Assigned Gmail"],
                ["Jane Smith", "jane@personal.com", "555-5678", "jane.smith@gmail.com"],
            ]
        }

        mock_drive = MagicMock()
        client._drive_service = mock_drive
        mock_drive.files().list().execute.return_value = {
            "files": [{"id": "sheet1", "name": "Student Info"}]
        }

        result = client.read_student_spreadsheet("folder1")

        assert result is not None
        assert result["full_name"] == "Jane Smith"
        assert result["personal_email"] == "jane@personal.com"

    def test_no_spreadsheet_in_folder(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )

        mock_drive = MagicMock()
        client._drive_service = mock_drive
        mock_drive.files().list().execute.return_value = {"files": []}

        result = client.read_student_spreadsheet("folder1")
        assert result is None

    def test_empty_spreadsheet(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )

        mock_sheets = MagicMock()
        client._sheets_service = mock_sheets
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": []
        }

        mock_drive = MagicMock()
        client._drive_service = mock_drive
        mock_drive.files().list().execute.return_value = {
            "files": [{"id": "sheet1", "name": "Info"}]
        }

        result = client.read_student_spreadsheet("folder1")
        assert result is None


class TestGoogleDriveClientGetStudentInfo:
    """Test the full student lookup pipeline."""

    def test_full_lookup_success(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )

        # Pre-populate folder cache
        client._cache.set_folder_list(
            [{"id": "folder_john", "name": "john.doe"}]
        )

        # Mock Drive and Sheets services
        mock_drive = MagicMock()
        mock_sheets = MagicMock()
        client._drive_service = mock_drive
        client._sheets_service = mock_sheets

        mock_drive.files().list().execute.return_value = {
            "files": [{"id": "sheet_john", "name": "John Info"}]
        }
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["Full Name", "John Doe"],
                ["Personal Email", "john@hotmail.com"],
                ["Assigned Gmail", "john.doe@gmail.com"],
                ["Phone", "555-9999"],
            ]
        }

        result = client.get_student_info("john.doe")

        assert result is not None
        assert result["full_name"] == "John Doe"
        assert result["personal_email"] == "john@hotmail.com"
        assert result["_username"] == "john.doe"
        assert result["_folder_id"] == "folder_john"

    def test_cached_result_returned(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )

        # Pre-populate cache
        cached_data = {
            "full_name": "Cached User",
            "personal_email": "cached@test.com",
        }
        client._cache.set("cached_user", cached_data)

        result = client.get_student_info("cached_user")
        assert result == cached_data

    def test_no_folder_found(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )
        client._cache.set_folder_list([])

        result = client.get_student_info("nonexistent")
        assert result is None

    def test_clear_cache(self):
        client = GoogleDriveClient(
            service_account_key_path="/fake/key.json",
            students_folder_id="root",
        )
        client._cache.set("user", {"test": True})
        client.clear_cache()
        assert client._cache.get("user") is None
