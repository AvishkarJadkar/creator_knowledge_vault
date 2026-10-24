"""Drop the throwaway Postgres database used by the smoke suite."""
import os

import psycopg2

url = os.environ["PGURL"]
admin = psycopg2.connect(url)
admin.autocommit = True
cur = admin.cursor()
cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname='vaulty_test' and pid <> pg_backend_pid()")
cur.execute("drop database if exists vaulty_test")
admin.close()
print("dropped vaulty_test")
