import sqlite3

try:
    conn = sqlite3.connect('vault.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(social_profile)")
    columns = cursor.fetchall()
    print("Columns in social_profile:")
    for col in columns:
        print(f" - {col[1]} ({col[2]})")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
