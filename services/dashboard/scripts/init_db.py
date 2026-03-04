"""
Initialize the database with tables and seed data.

This script:
1. Creates all database tables if they don't exist
2. Imports existing whitelist companies from process_inbox_auto.py
3. Optionally imports historical summary.json files

Usage:
    python init_db.py [--import-summaries]
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from database import engine, SessionLocal, init_db
from models import WhitelistCompany, ProcessRun
from config import settings


def import_whitelist():
    """
    Import KNOWN_INTERVIEW_COMPANIES from process_inbox_auto.py into database.
    """
    print("Importing whitelist companies...")

    # Import the whitelist from execution script
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "execution"))
    from process_inbox_auto import KNOWN_INTERVIEW_COMPANIES

    db = SessionLocal()
    try:
        imported = 0
        for company_name in KNOWN_INTERVIEW_COMPANIES:
            # Check if already exists
            existing = db.query(WhitelistCompany).filter(
                WhitelistCompany.company_name == company_name
            ).first()

            if not existing:
                whitelist_entry = WhitelistCompany(
                    company_name=company_name,
                    added_by="system",
                    notes="Imported from process_inbox_auto.py"
                )
                db.add(whitelist_entry)
                imported += 1

        db.commit()
        print(f"Imported {imported} whitelist companies")

    finally:
        db.close()


def import_summary_files():
    """
    Import historical summary.json files into the database.
    """
    print("Importing historical summary files...")

    tmp_dir = Path(__file__).parent.parent.parent.parent / "tmp"
    summary_files = list(tmp_dir.glob("auto_process_*/summary.json"))

    print(f"Found {len(summary_files)} summary files")

    db = SessionLocal()
    try:
        imported = 0
        for summary_file in summary_files:
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            stats = data.get("statistics", {})
            timestamp_str = stats.get("timestamp", "")

            # Parse timestamp from folder name (e.g., auto_process_20260128_082111)
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except:
                print(f"Skipping {summary_file} - invalid timestamp format")
                continue

            # Check if already imported
            existing = db.query(ProcessRun).filter(
                ProcessRun.run_timestamp == timestamp
            ).first()

            if existing:
                print(f"Skipping {summary_file} - already imported")
                continue

            # Create ProcessRun record
            process_run = ProcessRun(
                run_timestamp=timestamp,
                total_emails=stats.get("total_emails", 0),
                interview_requests=stats.get("interview_requests", 0),
                organized=stats.get("organized", 0),
                spam_deleted=stats.get("spam_deleted", 0),
                categories_breakdown=stats.get("categories", {}),
                status="success"
            )

            db.add(process_run)
            imported += 1

        db.commit()
        print(f"Imported {imported} process runs")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Initialize Email Dashboard Database")
    parser.add_argument(
        "--import-summaries",
        action="store_true",
        help="Import historical summary.json files"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Email Dashboard - Database Initialization")
    print("=" * 60)
    print()

    print(f"Database URL: {settings.database_url}")
    print()

    # Create all tables
    print("Creating database tables...")
    init_db()
    print("Database tables created successfully")
    print()

    # Import whitelist
    import_whitelist()
    print()

    # Optionally import historical summaries
    if args.import_summaries:
        import_summary_files()
        print()

    print("=" * 60)
    print("Database initialization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Generate admin password hash: python scripts/generate_password_hash.py")
    print("2. Add ADMIN_PASSWORD_HASH to .env file")
    print("3. Start the API: python api/main.py")
    print()


if __name__ == "__main__":
    main()
