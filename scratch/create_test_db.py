"""Create a throwaway Postgres database for running the smoke suite against it."""
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import psycopg2

url = os.environ["PGURL"]
admin = psycopg2.connect(url)
admin.autocommit = True
cur = admin.cursor()
cur.execute("select 1 from pg_database where datname='vaulty_test'")
if cur.fetchone():
    cur.execute("drop database vaulty_test")
cur.execute("create database vaulty_test")
admin.close()

test_url = urlunsplit(urlsplit(url)._replace(path="/vaulty_test"))
out = os.path.join(os.environ["TEMP"], "vaulty_test_url.txt")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(test_url)
print("created vaulty_test ->", out)
