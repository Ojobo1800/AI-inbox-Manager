"""
Test configuration loading and basic setup.

These tests verify that the configuration, models, and auth
modules can be imported and initialized correctly.
"""

import sys
from pathlib import Path

# Add api directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))


def test_config_import():
    """Test that config module can be imported and settings loaded."""
    from config import settings

    assert settings.app_name == "Email Management Dashboard"
    assert settings.environment in ["development", "production"]
    assert settings.database_url is not None
    print("[PASS] Config module loads correctly")


def test_models_import():
    """Test that all models can be imported."""
    from models import (
        Email, Classification, Approval, ProcessRun,
        WhitelistCompany, EmailAction, UserSession, SystemConfig
    )

    assert Email.__tablename__ == "emails"
    assert Classification.__tablename__ == "classifications"
    assert Approval.__tablename__ == "approvals"
    assert ProcessRun.__tablename__ == "process_runs"
    assert WhitelistCompany.__tablename__ == "whitelist_companies"
    assert EmailAction.__tablename__ == "email_actions"
    assert UserSession.__tablename__ == "user_sessions"
    assert SystemConfig.__tablename__ == "system_config"

    print("[PASS] All models import correctly")


def test_auth_functions():
    """Test password hashing and verification."""
    from auth import hash_password, verify_password

    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)

    print("[PASS] Password hashing and verification work")


def test_database_base():
    """Test that database Base is configured correctly."""
    from database import Base

    assert Base is not None
    assert hasattr(Base, 'metadata')

    print("[PASS] Database Base configured correctly")


def test_app_creation():
    """Test that FastAPI app can be created."""
    from main import app

    assert app is not None
    assert app.title == "Email Management Dashboard"

    print("[PASS] FastAPI app creates successfully")


if __name__ == "__main__":
    print("=" * 60)
    print("Backend Foundation Tests")
    print("=" * 60)
    print()

    try:
        test_config_import()
        test_models_import()
        test_auth_functions()
        test_database_base()
        test_app_creation()

        print()
        print("=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        print()
        print("Backend foundation is working correctly!")
        print()
        print("Next steps:")
        print("1. Start PostgreSQL: docker-compose up -d postgres")
        print("2. Initialize database: python scripts/init_db.py")
        print("3. Start API: python api/main.py")

    except Exception as e:
        print()
        print("=" * 60)
        print(f"TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
