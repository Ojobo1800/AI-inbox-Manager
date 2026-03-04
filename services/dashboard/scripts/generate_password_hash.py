"""
Generate a bcrypt password hash for the admin user.

Usage:
    python generate_password_hash.py

This will prompt for a password and output the bcrypt hash
that should be set in the ADMIN_PASSWORD_HASH environment variable.
"""

import sys
import getpass

# Add parent directory to path to import auth module
sys.path.insert(0, '../api')

from auth import hash_password


def main():
    print("=" * 60)
    print("Email Dashboard - Generate Admin Password Hash")
    print("=" * 60)
    print()

    password = getpass.getpass("Enter admin password: ")
    password_confirm = getpass.getpass("Confirm admin password: ")

    if password != password_confirm:
        print("ERROR: Passwords do not match")
        sys.exit(1)

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters")
        sys.exit(1)

    print()
    print("Generating hash (this may take a few seconds)...")
    hashed = hash_password(password)

    print()
    print("=" * 60)
    print("PASSWORD HASH GENERATED")
    print("=" * 60)
    print()
    print("Add this line to your .env file:")
    print()
    print(f"ADMIN_PASSWORD_HASH={hashed}")
    print()
    print("IMPORTANT: Keep this hash secure. Anyone with this hash")
    print("can authenticate to the dashboard.")
    print("=" * 60)


if __name__ == "__main__":
    main()
