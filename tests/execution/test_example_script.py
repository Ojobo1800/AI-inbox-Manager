"""
Unit tests for example_script.py

Demonstrates best practices for testing execution layer code.
"""

import pytest
import json
from pathlib import Path
from execution.example_script import process_data, load_input, save_output


class TestProcessData:
    """Test the core business logic."""

    def test_process_valid_records(self):
        """Test processing with all valid records."""
        records = [
            {"id": "1", "value": 10},
            {"id": "2", "value": 20},
        ]

        result = process_data(records)

        assert result["total_count"] == 2
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["processed_records"]) == 2
        assert result["processed_records"][0]["value"] == 20  # 10 * 2
        assert result["processed_records"][1]["value"] == 40  # 20 * 2

    def test_process_records_missing_id(self):
        """Test handling of records missing required 'id' field."""
        records = [
            {"id": "1", "value": 10},
            {"value": 20},  # Missing id
        ]

        result = process_data(records)

        assert result["total_count"] == 2
        assert result["success_count"] == 1
        assert result["error_count"] == 1
        assert "missing required field 'id'" in result["errors"][0]

    def test_process_empty_list(self):
        """Test processing an empty list of records."""
        result = process_data([])

        assert result["total_count"] == 0
        assert result["success_count"] == 0
        assert result["error_count"] == 0
        assert result["processed_records"] == []

    def test_default_value_handling(self):
        """Test that missing 'value' field defaults to 0."""
        records = [{"id": "1"}]  # No value field

        result = process_data(records)

        assert result["success_count"] == 1
        assert result["processed_records"][0]["value"] == 0  # 0 * 2


class TestLoadInput:
    """Test file loading functionality."""

    def test_load_valid_json(self, temp_dir):
        """Test loading a valid JSON file."""
        test_file = temp_dir / "input.json"
        test_data = [{"id": "1", "value": 10}]

        with open(test_file, 'w') as f:
            json.dump(test_data, f)

        result = load_input(test_file)

        assert result == test_data

    def test_load_nonexistent_file(self, temp_dir):
        """Test that loading a non-existent file raises FileNotFoundError."""
        missing_file = temp_dir / "missing.json"

        with pytest.raises(FileNotFoundError):
            load_input(missing_file)


class TestSaveOutput:
    """Test file saving functionality."""

    def test_save_creates_file(self, temp_dir):
        """Test that save_output creates the output file."""
        output_file = temp_dir / "output.json"
        results = {
            "processed_records": [{"id": "1"}],
            "success_count": 1
        }

        save_output(results, output_file)

        assert output_file.exists()
        with open(output_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == results

    def test_save_creates_directory(self, temp_dir):
        """Test that save_output creates parent directories if needed."""
        output_file = temp_dir / "nested" / "dir" / "output.json"
        results = {"success_count": 0}

        save_output(results, output_file)

        assert output_file.exists()
        assert output_file.parent.exists()


class TestIntegration:
    """Integration tests that combine multiple functions."""

    def test_full_pipeline(self, temp_dir):
        """Test the complete load -> process -> save pipeline."""
        # Setup
        input_file = temp_dir / "input.json"
        output_file = temp_dir / "output.json"
        test_data = [
            {"id": "1", "value": 5},
            {"id": "2", "value": 10},
        ]

        with open(input_file, 'w') as f:
            json.dump(test_data, f)

        # Execute
        records = load_input(input_file)
        results = process_data(records)
        save_output(results, output_file)

        # Verify
        assert output_file.exists()
        with open(output_file, 'r') as f:
            saved = json.load(f)

        assert saved["success_count"] == 2
        assert saved["processed_records"][0]["value"] == 10  # 5 * 2
        assert saved["processed_records"][1]["value"] == 20  # 10 * 2
