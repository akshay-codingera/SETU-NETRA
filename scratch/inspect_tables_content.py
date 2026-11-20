import sqlite3, json

def inspect_db(path):
    print(f"\n==========================================")
    print(f"DATABASE: {path}")
    print(f"==========================================")
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Check tables
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    print(f"Tables: {tables}")
    
    if "documents" in tables:
        docs = cursor.execute("SELECT doc_id, file_path, file_name, file_type, page_count, status FROM documents;").fetchall()
        print(f"\nDocuments ({len(docs)}):")
        for d in docs:
            print(f"  doc_id={d[0]}, file_name={d[2]}, type={d[3]}, pages={d[4]}, status={d[5]}, path={d[1]}")
            
    if "pages" in tables:
        pages = cursor.execute("SELECT page_id, doc_id, page_number, width, height, metadata_json FROM pages;").fetchall()
        print(f"\nPages ({len(pages)}):")
        for p in pages:
            print(f"  page_id={p[0]}, doc_id={p[1]}, page_num={p[2]}, dims={p[3]}x{p[4]}, meta={p[5]}")

    if "document_blocks" in tables:
        blocks = cursor.execute("SELECT block_pk, doc_id, page_number, block_id, block_type, text, confidence, bbox_json, embedding_dim, embedding_engine FROM document_blocks;").fetchall()
        print(f"\nDocument Blocks ({len(blocks)}):")
        for b in blocks:
            text_preview = b[5][:60].replace('\n', ' ') if b[5] else ''
            print(f"  pk={b[0]}, doc={b[1]}, pg={b[2]}, blk_id={b[3]}, type={b[4]}, conf={b[6]:.2f}, dim={b[8]}, bbox={b[7]}, text='{text_preview}'")

for db_path in [
    'output/setu_netra.db',
    'output/test_phase1.db',
    'output/v1_1_benchmark_store.db',
    'output/acceptance_test.db',
    'output/e2e_verify/e2e_netra.db'
]:
    try:
        inspect_db(db_path)
    except Exception as e:
        print(f"Error inspecting {db_path}: {e}")
