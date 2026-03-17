import sqlite3
import os

db_path = 'instance/vault.db'

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

try:
    print("Checking for is_deleted column in content table...")
    cursor.execute("PRAGMA table_info(content)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'is_deleted' not in columns:
        print("Adding is_deleted column to content table...")
        cursor.execute("ALTER TABLE content ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0")
        connection.commit()
        print("Successfully added is_deleted column.")
    else:
        print("Column is_deleted already exists.")
        
except Exception as e:
    print(f"Error during migration: {e}")
    connection.rollback()
finally:
    connection.close()
