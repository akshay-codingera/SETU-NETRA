import sqlite3, json

conn = sqlite3.connect('output/setu_netra.db')
cur = conn.cursor()
pages = cur.execute("SELECT page_id, doc_id, page_number, width, height, metadata_json FROM pages;").fetchall()
print(f"Total pages in output/setu_netra.db: {len(pages)}")
for p in pages:
    meta = json.loads(p[5]) if p[5] else {}
    print(f"\nPage: {p[0]} (doc={p[1]}, dims={p[3]}x{p[4]})")
    print(f"  Meta keys: {list(meta.keys())}")
    if "detected_questions" in meta:
        print(f"  Detected questions count: {len(meta['detected_questions'])}")
        for q in meta['detected_questions']:
            print(f"    - Q: {q.get('question_text', '')[:60]} | Opts: {len(q.get('options', []))}")
    if "ocr_boxes_count" in meta:
        print(f"  OCR boxes count: {meta['ocr_boxes_count']}")
