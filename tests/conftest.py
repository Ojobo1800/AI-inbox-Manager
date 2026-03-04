"""
Shared pytest configuration and fixtures.

This file is automatically loaded by pytest and provides common fixtures
for all test files.
"""

import os
import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def mock_env(monkeypatch):
    """Fixture to easily mock environment variables."""
    def _set_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, str(value))
    return _set_env


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Ensure tests run in dev mode by default."""
    monkeypatch.setenv("ENVIRONMENT", "test")

    # Prevent accidental production access
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("Tests must never run against production!")


@pytest.fixture
def sample_data():
    """Provide sample test data."""
    return {
        "test_key": "test_value",
        "items": [1, 2, 3],
        "nested": {
            "value": "example"
        }
    }
