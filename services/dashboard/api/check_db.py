import sqlite3

for path in [
    'email_dashboard.db',
    '../email_dashboard.db',
    '../../email_dashboard.db',
]:
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"\n{path}: tables = {tables}")
        if 'users' in tables:
            cur.execute("SELECT id, username, is_active FROM users")
            rows = cur.fetchall()
            print(f"  users: {rows}")
        conn.close()
    except Exception as e:
        print(f"{path}: ERROR - {e}")
