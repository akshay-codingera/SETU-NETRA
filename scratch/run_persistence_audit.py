"""
run_persistence_audit.py: Empirical persistence and stress audit for SETU-NETRA SQLiteDocumentStore.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
import numpy as np

from setu_netra.store.sqlite_store import SQLiteDocumentStore, compute_file_sha256


def run_audit():
    print("=" * 70)
    print("  SETU-NETRA: PERSISTENCE & DATA INTEGRITY AUDIT")
    print("=" * 70)
    temp_dir = Path(tempfile.mkdtemp(prefix="setu_persist_audit_"))
    db_path = temp_dir / "audit_store.db"

    results = {}

    try:
        # --- TEST 1: Database Creation & PRAGMA Configuration ---
        print("\n[TEST 1] Database Creation & PRAGMA Configuration...")
        store = SQLiteDocumentStore(db_path)
        cur = store._conn.cursor()
        journal_mode = cur.execute("PRAGMA journal_mode;").fetchone()[0]
        sync_mode = cur.execute("PRAGMA synchronous;").fetchone()[0]
        fk_mode = cur.execute("PRAGMA foreign_keys;").fetchone()[0]
        
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        indices = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()]
        
        print(f"  - Journal Mode: {journal_mode} (Expected: wal)")
        print(f"  - Synchronous Mode: {sync_mode} (Expected: 1 / NORMAL)")
        print(f"  - Foreign Keys: {fk_mode} (Expected: 1 / ON)")
        print(f"  - Tables: {tables}")
        print(f"  - Indices: {indices}")
        results["test1_pragma"] = {
            "journal_mode": journal_mode,
            "synchronous": sync_mode,
            "foreign_keys": fk_mode,
            "tables": tables,
            "indices": indices,
        }

        # --- TEST 2: Repeated Ingestion & SHA-256 Deduplication ---
        print("\n[TEST 2] Repeated Ingestion & Deduplication...")
        dummy_file = temp_dir / "test_doc.pdf"
        dummy_file.write_bytes(b"%PDF-1.4 dummy content for audit testing")
        file_hash = compute_file_sha256(dummy_file)

        doc1 = store.save_document("doc_001", dummy_file, file_hash, "PDF", page_count=2)
        existing1 = store.get_document_by_hash(file_hash)
        doc2 = store.save_document("doc_001", dummy_file, file_hash, "PDF", page_count=2)
        
        doc_count = cur.execute("SELECT COUNT(*) FROM documents;").fetchone()[0]
        print(f"  - Original Doc ID: {doc1.doc_id}")
        print(f"  - Query by Hash Found: {existing1.doc_id if existing1 else None}")
        print(f"  - Rows in documents table after duplicate insert: {doc_count} (Expected: 1)")
        results["test2_dedup"] = {
            "hash": file_hash,
            "doc_count": doc_count,
            "dedup_success": (doc_count == 1 and existing1.doc_id == "doc_001"),
        }

        # --- TEST 3: DB Restart & Data Roundtrip ---
        print("\n[TEST 3] Database Connection Restart & Roundtrip...")
        store.save_page("doc_001_p1", "doc_001", 1, 1200, 800)
        vec_orig = np.random.randn(384).astype(np.float32)
        vec_orig /= np.linalg.norm(vec_orig)
        
        blocks_data = [{
            "block_id": 1,
            "block_type": "QUESTION",
            "text": "Audit persistence question text",
            "confidence": 0.95,
            "bounding_box": (10.0, 20.0, 300.0, 80.0),
            "embedding": vec_orig,
            "embedding_engine": "neural_all-MiniLM-L6-v2",
        }]
        store.save_blocks("doc_001", 1, blocks_data)
        
        # Simulate restart
        store.close()
        store2 = SQLiteDocumentStore(db_path)
        
        doc_restored = store2.get_document_by_id("doc_001")
        pages_restored = store2.get_pages("doc_001")
        blocks_restored = store2.get_blocks("doc_001")
        meta_list, matrix_restored = store2.get_all_embeddings("neural_all-MiniLM-L6-v2")
        
        vec_diff = np.max(np.abs(vec_orig - matrix_restored[0]))
        print(f"  - Restored Doc: {doc_restored.doc_id if doc_restored else None}")
        print(f"  - Restored Pages Count: {len(pages_restored)}")
        print(f"  - Restored Blocks Count: {len(blocks_restored)}")
        print(f"  - Embedding Matrix Shape: {matrix_restored.shape}")
        print(f"  - Max Float32 Difference: {vec_diff:.10e} (Expected: 0.0)")
        results["test3_restart"] = {
            "restored": doc_restored is not None,
            "pages_count": len(pages_restored),
            "blocks_count": len(blocks_restored),
            "max_float_diff": float(vec_diff),
        }

        # --- TEST 4: Transaction Rollback Verification ---
        print("\n[TEST 4] Transaction Rollback on Failure...")
        before_count = store2._conn.execute("SELECT COUNT(*) FROM pages;").fetchone()[0]
        try:
            with store2._conn:
                store2._conn.execute(
                    "INSERT INTO pages (page_id, doc_id, page_number, width, height) VALUES (?, ?, ?, ?, ?);",
                    ("page_valid", "doc_001", 2, 1000, 800)
                )
                # Force failure: foreign key violation with non-existent doc
                store2._conn.execute(
                    "INSERT INTO pages (page_id, doc_id, page_number, width, height) VALUES (?, ?, ?, ?, ?);",
                    ("page_invalid", "doc_NON_EXISTENT_XYZ", 3, 1000, 800)
                )
        except sqlite3.IntegrityError as err:
            print(f"  - Caught Expected IntegrityError: {err}")

        after_count = store2._conn.execute("SELECT COUNT(*) FROM pages;").fetchone()[0]
        print(f"  - Page Count Before Failed Tx: {before_count}")
        print(f"  - Page Count After Rollback:   {after_count} (Expected: {before_count})")
        results["test4_rollback"] = {
            "before": before_count,
            "after": after_count,
            "rolled_back": (before_count == after_count),
        }

        # --- TEST 5: Corrupted & Missing Records Handling ---
        print("\n[TEST 5] Corrupted and Missing Records Handling...")
        # 5a. Missing query
        missing_doc = store2.get_document_by_id("non_existent_doc_id_999")
        missing_hash = store2.get_document_by_hash("fake_hash_999")
        print(f"  - Query Missing Doc ID: {missing_doc} (Expected: None)")
        print(f"  - Query Missing Hash:   {missing_hash} (Expected: None)")

        # 5b. Corrupt record insertion: insert truncated embedding blob
        with store2._conn:
            store2._conn.execute(
                """
                INSERT INTO document_blocks (
                    doc_id, page_number, block_id, block_type, text, confidence,
                    bbox_json, embedding_blob, embedding_dim, embedding_engine
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "doc_001", 1, 99, "PARAGRAPH", "Corrupted block", 0.5,
                    "[0,0,10,10]", b"\x00\x01\x02", 3, "neural_all-MiniLM-L6-v2"
                )
            )

        # What happens when unpacking?
        try:
            meta_list_corrupt, matrix_corrupt = store2.get_all_embeddings("neural_all-MiniLM-L6-v2")
            print(f"  - Embedding retrieval handled corrupt blob: {len(meta_list_corrupt)} items")
            results["test5_corrupted"] = {
                "crashed": False,
                "meta_count": len(meta_list_corrupt),
            }
        except ValueError as err:
            print(f"  - [VULNERABILITY CONFIRMED] Unpacking corrupt blob crashed with: {err}")
            results["test5_corrupted"] = {
                "crashed": True,
                "error": str(err),
                "vulnerability": "Single corrupted embedding blob crashes entire get_all_embeddings() query",
            }
            # Clean up corrupted row so subsequent tests can continue
            with store2._conn:
                store2._conn.execute("DELETE FROM document_blocks WHERE block_id = 99;")

        # --- TEST 6: Concurrent Multi-Threaded Read/Write ---
        print("\n[TEST 6] Concurrent Multi-Threaded Read/Write Stress (WAL Mode)...")
        errors = []
        stop_event = threading.Event()

        def reader_worker(worker_id):
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            reads = 0
            while not stop_event.is_set():
                try:
                    cur = conn.execute("SELECT COUNT(*) FROM document_blocks;")
                    _ = cur.fetchone()[0]
                    reads += 1
                    time.sleep(0.005)
                except Exception as e:
                    errors.append(f"Reader {worker_id} error: {e}")
                    break
            conn.close()

        def writer_worker(worker_id):
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            writes = 0
            while not stop_event.is_set() and writes < 30:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO documents (doc_id, file_path, file_name, file_hash, file_type, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?);",
                            (f"conc_doc_{worker_id}_{writes}", "dummy.pdf", f"dummy_{worker_id}_{writes}.pdf",
                             f"hash_{worker_id}_{writes}_{time.time()}", "PDF", "2026-11-03T00:00:00")
                        )
                    writes += 1
                    time.sleep(0.01)
                except Exception as e:
                    errors.append(f"Writer {worker_id} error: {e}")
                    break
            conn.close()

        threads = []
        for i in range(3):
            t = threading.Thread(target=reader_worker, args=(i,))
            threads.append(t)
        for i in range(2):
            t = threading.Thread(target=writer_worker, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()

        time.sleep(1.0)
        stop_event.set()
        for t in threads:
            t.join()

        print(f"  - Concurrent Read/Write Errors: {len(errors)}")
        if errors:
            for e in errors[:5]:
                print(f"    [!] {e}")
        results["test6_concurrency"] = {
            "error_count": len(errors),
            "errors": errors[:5],
        }

        store2.close()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    print("  PERSISTENCE AUDIT EXECUTION COMPLETE")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_audit()
