import sys
sys.path.insert(0, '.')

from config import settings
import bcrypt

print(f"admin_password_hash = '{settings.admin_password_hash}'")
print(f"hash length = {len(settings.admin_password_hash) if settings.admin_password_hash else 0}")

if settings.admin_password_hash:
    try:
        result = bcrypt.checkpw(b"admin123", settings.admin_password_hash.encode('utf-8'))
        print(f"Password 'admin123' matches hash: {result}")
    except Exception as e:
        print(f"bcrypt error: {e}")
        print("Hash may be malformed - regenerating...")
        new_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=12)).decode('utf-8')
        print(f"\nNew hash for admin123:\n{new_hash}")
        print(f"\nUpdate your .env ADMIN_PASSWORD_HASH to this value.")
else:
    print("ERROR: ADMIN_PASSWORD_HASH is not set!")
    new_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=12)).decode('utf-8')
    print(f"\nGenerated hash for admin123:\n{new_hash}")
