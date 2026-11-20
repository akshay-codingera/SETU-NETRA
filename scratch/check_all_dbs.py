import sqlite3, glob

for db_path in glob.glob("output/**/*.db", recursive=True) + glob.glob("output/*.db"):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        if "documents" in tables:
            d_cnt = cur.execute("SELECT count(*) FROM documents;").fetchone()[0]
            p_cnt = cur.execute("SELECT count(*) FROM pages;").fetchone()[0] if "pages" in tables else 0
            b_cnt = cur.execute("SELECT count(*) FROM document_blocks;").fetchone()[0] if "document_blocks" in tables else 0
            print(f"{db_path}: {d_cnt} docs, {p_cnt} pages, {b_cnt} blocks")
        else:
            print(f"{db_path}: tables={tables}")
    except Exception as e:
        print(f"Error {db_path}: {e}")
