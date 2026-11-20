import sys
import threading
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.ui.app import start_server

def http_get(url: str):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        return response.status, response.read().decode("utf-8")

def http_post_json(url: str, data: dict):
    json_bytes = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=json_bytes,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        return response.status, json.loads(response.read().decode("utf-8"))

def test_full_application_workflow():
    port = 8599
    db_path = "output/e2e_verify/e2e_netra.db"
    
    print(f"Starting SETU-NETRA test server on port {port} with DB {db_path}...")
    server = start_server(port=port, db_path=db_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(1.0)
    
    base_url = f"http://127.0.0.1:{port}"
    
    try:
        # 1. Test GET / (HTML UI)
        status, text = http_get(f"{base_url}/")
        assert status == 200, f"UI status code: {status}"
        assert "SETU-NETRA" in text
        print("[OK] GET / returns 200 and loads HTML template.")

        # 2. Test GET /api/documents
        status, docs_json_str = http_get(f"{base_url}/api/documents")
        assert status == 200, f"Docs status code: {status}"
        docs_data = json.loads(docs_json_str)
        docs = docs_data.get("documents", [])
        print(f"[OK] GET /api/documents returned {len(docs)} documents.")
        for d in docs:
            print(f"     Doc: {d.get('doc_id')} | {d.get('filename')} | {d.get('file_type')} | {d.get('page_count')} pages")

        # 3. Test GET /api/document/<doc_id>/questions
        if docs:
            sample_doc = docs[0]["doc_id"]
            status, q_json_str = http_get(f"{base_url}/api/document/{sample_doc}/questions")
            assert status == 200
            q_data = json.loads(q_json_str)
            questions = q_data.get("questions", [])
            print(f"[OK] GET /api/document/{sample_doc}/questions returned {len(questions)} extracted questions.")

        # 4. Test POST /api/query (Document-to-Answer-to-Citation)
        query_payload = {
            "query": "How does the Raft consensus algorithm establish consistency across nodes?",
            "doc_id": "doc_consensus_8c698d88"
        }
        status, qa_data = http_post_json(f"{base_url}/api/query", query_payload)
        assert status == 200, f"QA query status code: {status}"
        print("[OK] POST /api/query returned 200:")
        print(f"     Answer:    {qa_data.get('answer_text')}")
        print(f"     Status:    {qa_data.get('epistemic_status')}")
        print(f"     Model:     {qa_data.get('executing_model_id')}")
        print(f"     Latency:   {qa_data.get('execution_time_ms')} ms")
        print(f"     Citations: {qa_data.get('citations')}")
        assert qa_data.get("epistemic_status") == "EVIDENCE_BACKED"
        assert len(qa_data.get("citations", [])) > 0
        print("[OK] End-to-end Document-to-Answer-to-Citation workflow fully verified!")

    finally:
        server.shutdown()
        server.server_close()
        print("Server shutdown completed.")

if __name__ == "__main__":
    test_full_application_workflow()
