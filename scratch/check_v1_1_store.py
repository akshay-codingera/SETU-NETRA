import sqlite3

conn = sqlite3.connect('output/v1_1_benchmark_store.db')
cur = conn.cursor()
docs = cur.execute("SELECT doc_id, file_name, file_type, page_count, status FROM documents;").fetchall()
print(f"Docs in v1_1_benchmark_store.db: {len(docs)}")
for d in docs:
    print(f"  {d}")

blocks = cur.execute("SELECT block_pk, doc_id, page_number, block_id, block_type, text, confidence, bbox_json, embedding_dim FROM document_blocks;").fetchall()
print(f"\nBlocks in v1_1_benchmark_store.db: {len(blocks)}")
for b in blocks:
    print(f"  [pk={b[0]}, doc={b[1]}, pg={b[2]}, id={b[3]}, type={b[4]}, dim={b[8]}, bbox={b[7]}]: {b[5][:60]}")
