import sqlite3

db_path = 'instance/vault.db'
try:
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in database:")
    for table in tables:
        print(f" - {table[0]}")
    connection.close()
except Exception as e:
    print(f"Error listing tables: {e}")
