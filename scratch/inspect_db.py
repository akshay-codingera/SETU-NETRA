import sqlite3

conn = sqlite3.connect('output/setu_netra.db')
cursor = conn.cursor()
tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
print("TABLES in output/setu_netra.db:")
for t in tables:
    count = cursor.execute(f"SELECT count(*) FROM {t};").fetchone()[0]
    print(f"  - {t}: {count} rows")

print("\nSCHEMA for each table:")
for t in tables:
    print(f"\n--- Table: {t} ---")
    schema = cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}';").fetchone()[0]
    print(schema)
