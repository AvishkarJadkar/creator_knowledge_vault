import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

def migrate_sqlite():
    db_path = "instance/vault.db"
    if not os.path.exists(db_path):
        print(f"No SQLite database found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting SQLite migration...")

    # Tables to migrate user_id from INTEGER to TEXT
    tables = ["content", "social_profile", "chat_session", "memory"]

    for table in tables:
        try:
            print(f"Migrating table: {table}")
            # SQLite doesn't support easy ALTER COLUMN type. 
            # We'll create a new temp table, copy data, and rename.
            
            # 1. Get current schema
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            # Construct new column definitions
            col_defs = []
            for col in columns:
                name, col_type, nullable, default, pk = col[1], col[2], col[3], col[4], col[5]
                new_type = col_type
                if name == "user_id":
                    new_type = "TEXT"
                
                col_def = f"{name} {new_type}"
                if pk: col_def += " PRIMARY KEY"
                if not nullable: col_def += " NOT NULL"
                if default is not None: 
                    col_def += f" DEFAULT {default}"
                elif name == "last_synced_video":
                    col_def += " DEFAULT ''"
                col_defs.append(col_def)
            
            # 2. Rename old, create new
            cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
            cursor.execute(f"CREATE TABLE {table} ({', '.join(col_defs)})")
            
            # 3. Copy data
            col_names = [c[1] for c in columns]
            cursor.execute(f"INSERT INTO {table} ({', '.join(col_names)}) SELECT {', '.join(col_names)} FROM {table}_old")
            
            # 4. Drop old
            cursor.execute(f"DROP TABLE {table}_old")
            print(f"Successfully migrated {table}")
        except Exception as e:
            print(f"Error migrating {table}: {e}")

    # Finally drop the User table as it's obsolete
    try:
        cursor.execute("DROP TABLE IF EXISTS user")
        print("Dropped obsolete 'user' table.")
    except Exception as e:
        print(f"Error dropping user table: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    # This specifically targets the local development SQLite DB.
    # For production (PostgreSQL), SQLAlchemy's db.create_all() will handle 
    # the new tables, but manual ALTER TABLE commands would be needed for type changes.
    migrate_sqlite()
