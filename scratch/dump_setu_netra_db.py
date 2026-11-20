import sqlite3, json

conn = sqlite3.connect('output/setu_netra.db')
cursor = conn.cursor()

docs = cursor.execute("SELECT doc_id, file_name, file_type, page_count, status FROM documents;").fetchall()
print(f"Total documents in output/setu_netra.db: {len(docs)}")
for d in docs:
    blocks = cursor.execute("SELECT block_pk, page_number, block_id, block_type, text, confidence, bbox_json, embedding_dim, source_detection_indices_json FROM document_blocks WHERE doc_id=?;", (d[0],)).fetchall()
    print(f"\nDocument: {d[1]} (id={d[0]}, type={d[2]}, pages={d[3]}, status={d[4]}, blocks={len(blocks)})")
    for b in blocks:
        print(f"  [pg {b[1]} | id {b[2]} | {b[3]} | conf {b[5]:.2f} | emb {b[7]}]: bbox={b[6]} | text: {b[4][:80]}")

print("\n--- Summary across output/setu_netra.db ---")
total_blocks = cursor.execute("SELECT count(*) FROM document_blocks;").fetchone()[0]
total_pages = cursor.execute("SELECT count(*) FROM pages;").fetchone()[0]
print(f"Total Documents: {len(docs)}")
print(f"Total Pages: {total_pages}")
print(f"Total Blocks: {total_blocks}")

# Block types breakdown
types = cursor.execute("SELECT block_type, count(*) FROM document_blocks GROUP BY block_type;").fetchall()
print(f"Block types: {types}")
