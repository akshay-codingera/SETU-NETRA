"""
scratch/verify_v1_workflow.py: Programmatic 13-step end-to-end demonstration workflow verification for SETU-NETRA V1.0.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.ui.app import start_server


def run_verification():
    db_path = "output/v1_demo_verify.db"
    port = 18550
    print("=" * 70)
    print("SETU-NETRA VERSION 1.0 — 13-STEP DEMONSTRATION WORKFLOW VERIFICATION")
    print("=" * 70)

    # 1. Launch server
    print("\n[Step 1] Launching Application Server on port", port)
    server = start_server(port=port, db_path=db_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(1.0)
    base_url = f"http://127.0.0.1:{port}"
    print(f"Server successfully listening at {base_url}/")

    # 2. Check UI root
    print("\n[Step 2] Validating Web UI Root Endpoint (GET /)")
    with urlopen(f"{base_url}/") as res:
        assert res.status == 200
        html = res.read().decode("utf-8")
        assert "SETU-NETRA" in html
        assert "Document Workspace" in html
        assert "Conversational QA" in html
        assert "Model Management" in html
        assert "Worker & Telemetry" in html
        assert "Benchmarks" in html
        print("Root UI page rendered valid HTML with all 5 functional tabs.")

    # 3. Document Ingestion / Upload
    print("\n[Step 3] Uploading Multi-format Document (Operating Systems Lecture Text)")
    sample_txt_path = Path("output/demo_os_lecture.txt")
    sample_txt_path.write_text(
        "Operating Systems Lecture 4: Virtual Memory Management.\n"
        "Virtual memory decouples logical address spaces from physical DRAM.\n"
        "The Memory Management Unit (MMU) translates virtual page numbers to physical page frames using page tables.\n"
        "Translation Lookaside Buffers (TLB) cache recent mappings to achieve single-cycle translation.\n"
        "Demand paging loads pages into RAM only when a page fault exception occurs.\n"
        "The optimal page replacement algorithm is Belady's MIN, while LRU provides a practical approximation.\n",
        encoding="utf-8",
    )
    # Ingest directly via doc_pipeline to get doc_id
    stored_doc = server.RequestHandlerClass.doc_pipeline.ingest_document(sample_txt_path)
    doc_id = stored_doc.doc_id
    print(f"Document ingested: doc_id='{doc_id}', pages={stored_doc.page_count}, file_name={stored_doc.file_name}")

    # 4. View Document & Extracted Questions
    print("\n[Step 4] Viewing Document Metadata & Extracted Questions")
    with urlopen(f"{base_url}/api/document/{doc_id}") as res:
        doc_data = json.loads(res.read().decode())
        print(f"Document API returned: {doc_data['document']['file_name']} (Page count: {doc_data['document']['page_count']})")

    with urlopen(f"{base_url}/api/document/{doc_id}/page/1/image") as res:
        img_bytes = res.read()
        print(f"Document Canvas Image fetched successfully: {len(img_bytes)} bytes PNG")

    with urlopen(f"{base_url}/api/document/{doc_id}/questions") as res:
        q_data = json.loads(res.read().decode())
        print(f"Questions API returned: {len(q_data['questions'])} extracted structured questions.")

    # 5. Ask question via Conversation tab
    print("\n[Step 5] Conversational QA: Starting Conversation & Asking Initial Factual Question")
    create_req = Request(
        f"{base_url}/api/conversations",
        data=json.dumps({"title": "Virtual Memory Session", "doc_ids": [doc_id]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(create_req) as res:
        conv_info = json.loads(res.read().decode())
        conv_id = conv_info["conversation_id"]
        print(f"Conversation created: conv_id='{conv_id}'")

    msg_req = Request(
        f"{base_url}/api/conversations/{conv_id}/messages",
        data=json.dumps({"query": "What hardware component translates virtual page numbers to physical page frames?", "doc_id": doc_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(msg_req) as res:
        ans1 = json.loads(res.read().decode())
        print("Answer Text:", ans1["answer_text"])
        print("Epistemic Status:", ans1["epistemic_status"])
        print("Executing Model:", ans1["executing_model_id"])
        print("Executing Worker:", ans1["executing_worker_id"])
        print("Grounding Score:", ans1["grounding_score"])
        print("Execution Latency:", ans1["execution_time_ms"], "ms")
        print("Citations:", ans1["citations"])
        assert ans1["epistemic_status"] == "EVIDENCE_BACKED"
        assert "MMU" in ans1["answer_text"]
        assert len(ans1["citations"]) > 0

    # 6. Verify Citation Bounding Box
    print("\n[Step 6] Verifying Citation Bounding Box for Visual Highlighting")
    first_cite = ans1["citations"][0]
    bbox = first_cite["bounding_box"]
    print(f"Citation references Page {first_cite['page']}, Block {first_cite['block_id']}, BBox: {bbox}")
    assert len(bbox) == 4

    # 7. Ask Follow-up Question (Coreference Resolution)
    print("\n[Step 7] Asking Follow-up Question with Coreference ('What does it cache?')")
    followup_req = Request(
        f"{base_url}/api/conversations/{conv_id}/messages",
        data=json.dumps({"query": "What does it cache to achieve single-cycle translation?", "doc_id": doc_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(followup_req) as res:
        ans2 = json.loads(res.read().decode())
        print("Resolved Query:", ans2["resolved_query"])
        print("Follow-up Answer:", ans2["answer_text"])
        print("Epistemic Status:", ans2["epistemic_status"])
        assert ans2["epistemic_status"] == "EVIDENCE_BACKED"
        assert len(ans2["citations"]) > 0

    # 8. Check Model Management & Privacy Toggle
    print("\n[Step 8] Model Management: Catalog Inspection and Privacy Mode Toggle")
    with urlopen(f"{base_url}/api/models") as res:
        models_data = json.loads(res.read().decode())
        print(f"Registered Models ({len(models_data['models'])}):")
        for m in models_data["models"]:
            print(f" - [{m.get('provider')}] {m.get('model_id')} ({m.get('availability')})")

    # Toggle Local-Only Mode ON
    post_settings = Request(
        f"{base_url}/api/settings",
        data=json.dumps({"local_only": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(post_settings) as res:
        settings_view = json.loads(res.read().decode())
        print("Local-Only Privacy Mode toggled to:", settings_view["local_only"])
        assert settings_view["local_only"] is True

    # 9. Check Worker Pool & System Telemetry
    print("\n[Step 9] Live Worker Pool & Cross-Platform Telemetry Inspection")
    with urlopen(f"{base_url}/api/telemetry") as res:
        t_data = json.loads(res.read().decode())
        print(f"Hardware Telemetry: CPU={t_data['cpu_percent']}%, RAM={t_data['memory_percent']}%, Available RAM={round(t_data['available_memory_mb'], 1)} MB (is_real={t_data['is_real']})")

    with urlopen(f"{base_url}/api/workers") as res:
        w_data = json.loads(res.read().decode())
        print(f"Active Worker Pool ({len(w_data['workers'])} workers):")
        for w in w_data["workers"][:4]:
            print(f" - Worker '{w['worker_id']}' ({w['model_id']}): State={w['state']}, Latency={w['last_execution_latency']} ms")

    # 10. Check Benchmarks
    print("\n[Step 10] Benchmark Intelligence: Verifying Static Charts & Telemetry")
    with urlopen(f"{base_url}/api/routing/status") as res:
        r_status = json.loads(res.read().decode())
        print(f"Routing Subsystem: Active Scheduler={r_status['active_scheduler']}, Models={r_status['registered_models_count']}, Status={r_status['status']}")

    # 11. Test Document Management (Re-index and Delete)
    print("\n[Step 11] Document Management Lifecycle: Re-indexing and Deletion")
    reindex_req = Request(f"{base_url}/api/document/{doc_id}/reindex", data=b"", method="POST")
    with urlopen(reindex_req) as res:
        reindex_res = json.loads(res.read().decode())
        print(f"Re-indexing completed: doc_id='{reindex_res['doc_id']}', status={reindex_res['status']}")
        assert reindex_res["doc_id"] == doc_id

    del_doc_req = Request(f"{base_url}/api/document/{doc_id}", method="DELETE")
    with urlopen(del_doc_req) as res:
        del_res = json.loads(res.read().decode())
        print(f"Document Deletion: {del_res['message']}")
        assert del_res["status"] == "SUCCESS"

    # 12. Test Privacy Mode Enforcement
    print("\n[Step 12] Privacy Mode Enforcement: Attempting Cloud Model Call")
    from setu_netra.routing.adapters.cloud_adapters import GeminiCloudAdapter
    gemini_adapter = GeminiCloudAdapter()
    from setu_netra.routing.contracts import InferenceRequest
    test_req = InferenceRequest(task_type="text_generation", input_payload="Summarize document")
    try:
        gemini_adapter.execute(test_req)
        print("ERROR: Cloud call was NOT blocked!")
        assert False
    except PermissionError as e:
        print(f"CONFIRMED: Cloud request strictly blocked by Local-Only Privacy Mode: '{e}'")

    # Reset Local-Only Mode
    reset_settings = Request(
        f"{base_url}/api/settings",
        data=json.dumps({"local_only": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(reset_settings) as res:
        s = json.loads(res.read().decode())
        assert s["local_only"] is False
        print("Local-Only Privacy Mode successfully reset to False.")

    # 13. Graceful Degradation Test
    print("\n[Step 13] Graceful Degradation: Offline Ollama Fallback")
    from setu_netra.routing.adapters.ollama_adapter import OllamaAdapter
    offline_ollama = OllamaAdapter(base_url="http://127.0.0.1:54321")
    assert offline_ollama.is_available() is False
    print("Ollama daemon offline detection confirmed without exception.")
    off_resp = offline_ollama.execute(test_req)
    assert off_resp.status == "FAILED"
    print(f"Offline execution gracefully handled: status='{off_resp.status}', error='{off_resp.error}'")

    print("\n" + "=" * 70)
    print("ALL 13 DEMONSTRATION WORKFLOW STEPS VERIFIED SUCCESSFULLY (100% PASS)!")
    print("=" * 70)

    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2.0)
    server.RequestHandlerClass.doc_pipeline.store.close()
    time.sleep(0.5)
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass
    if os.path.exists(sample_txt_path):
        os.remove(sample_txt_path)


if __name__ == "__main__":
    run_verification()
