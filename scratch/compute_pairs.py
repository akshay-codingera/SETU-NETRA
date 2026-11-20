import sqlite3, json
import numpy as np

conn = sqlite3.connect('output/setu_netra.db')
cur = conn.cursor()

# Get blocks per document and page
docs = cur.execute("SELECT DISTINCT doc_id, file_name FROM documents;").fetchall()
print(f"Unique docs in setu_netra.db: {len(docs)}")

total_candidate_edges = 0
for doc_id, file_name in docs:
    pages = cur.execute("SELECT DISTINCT page_number FROM document_blocks WHERE doc_id=?;", (doc_id,)).fetchall()
    for (pg,) in pages:
        blocks = cur.execute("SELECT block_id, block_type, bbox_json, text FROM document_blocks WHERE doc_id=? AND page_number=?;", (doc_id, pg)).fetchall()
        n = len(blocks)
        edges = n * (n - 1)
        total_candidate_edges += edges
        print(f"Doc: {file_name} (id={doc_id}) | Page: {pg} | Blocks: {n} | Directed Block Pairs: {edges}")

print(f"\nTotal Directed Block Pairs across output/setu_netra.db: {total_candidate_edges}")
