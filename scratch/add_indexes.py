import sqlite3
import os

db_path = 'instance/vault.db'
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

indexes = [
    ("ix_content_user_id", "content", "user_id"),
    ("ix_embedding_content_id", "embedding", "content_id"),
    ("ix_social_profile_user_id", "social_profile", "user_id"),
    ("ix_user_api_usage_composite", "user_api_usage", "user_id, api_type")
]

for name, table, col in indexes:
    print(f"Checking index {name}...")
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{name}'")
    if not cursor.fetchone():
        print(f"Creating index {name} on {table}({col})...")
        cursor.execute(f"CREATE INDEX {name} ON {table} ({col})")
    else:
        print(f"Index {name} already exists.")

conn.commit()
conn.close()
print("Done.")
