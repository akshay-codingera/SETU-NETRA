"""
query_runner.py: Deterministic QA evaluation runner for SETU-NETRA V1.1 benchmarks.
Executes the curated 100-query benchmark across the four 2x2 factorial conditions:
- Condition A: Fixed Model (SmolLM2) + Round Robin
- Condition B: Fixed Model (SmolLM2) + Capacity-Aware Scheduling
- Condition C: Adaptive Model Routing + Round Robin
- Condition D: Adaptive Model Routing + Capacity-Aware Scheduling
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from benchmarks.v1_1.harness.metrics import (
    compute_citation_precision,
    compute_exact_match,
    compute_percentiles_with_ci,
    compute_retrieval_metrics,
    compute_token_f1,
)
from setu_netra.core.contracts import RetrievedPassage
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.qa.engine import EvidenceGroundedQAEngine, VerifiedAnswer
from setu_netra.routing.contracts import InferenceRequest, InferenceResponse
from setu_netra.routing.pipeline import IntelligentInferencePipeline
from setu_netra.routing.registry import ModelRegistry, get_model_registry
from setu_netra.routing.schedulers.base import BaseScheduler
from setu_netra.routing.schedulers.capacity_aware import CapacityAwareScheduler
from setu_netra.routing.schedulers.round_robin import RoundRobinScheduler
from setu_netra.routing.system_telemetry import get_system_telemetry

logger = logging.getLogger(__name__)


class BenchmarkQAEngine(EvidenceGroundedQAEngine):
    """Subclass of QAEngine allowing deterministic fixed model targeting for Factorial Experiment."""

    def __init__(
        self,
        retriever,
        inference_pipeline: IntelligentInferencePipeline,
        fixed_model_id: Optional[str] = None,
    ):
        super().__init__(retriever=retriever, inference_pipeline=inference_pipeline)
        self.fixed_model_id = fixed_model_id

    def answer_question_benchmark(
        self,
        query: str,
        query_id: str,
        condition_name: str,
        doc_id: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.20,
    ) -> Tuple[VerifiedAnswer, Dict[str, Any]]:
        """Executes question answering and captures deep latency, queuing, and worker trace telemetry."""
        start_time = time.perf_counter()
        cleaned_query = query.strip()

        # 1. Retrieval
        passages = self.retriever.retrieve(
            query=cleaned_query,
            top_k=top_k,
            threshold=threshold,
            doc_id=doc_id,
            suppress_duplicates=True,
        )

        retrieval_elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Handle unsupported / no passages retrieved
        if not passages:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            ans = VerifiedAnswer(
                query=cleaned_query,
                answer_text="The uploaded document does not contain sufficient verified evidence to answer this question.",
                epistemic_status="UNSUPPORTED",
                citations=[],
                grounding_score=0.0,
                retrieved_passages=[],
                executing_model_id="none",
                execution_time_ms=round(elapsed_ms, 2),
                explanation="No passages passed the hybrid relevance threshold.",
            )
            telemetry = {
                "query_id": query_id,
                "correlation_id": f"TRACE_{condition_name}_{query_id}_{uuid.uuid4().hex[:6]}",
                "condition": condition_name,
                "routing_policy": "fixed" if self.fixed_model_id else "adaptive",
                "selected_model": "none",
                "selected_worker": "none",
                "queue_wait_ms": 0.0,
                "execution_time_ms": 0.0,
                "retrieval_time_ms": round(retrieval_elapsed_ms, 2),
                "total_latency_ms": round(elapsed_ms, 2),
                "status": "SUCCESS",
                "epistemic_status": "UNSUPPORTED",
                "http_status": 200,
            }
            return ans, telemetry

        # 2. Context Synthesis
        synthesized = self.synthesizer.synthesize(
            query=cleaned_query,
            passages=passages,
            max_budget_tokens=1500,
        )

        # 3. Model Inference via Unified Interface
        # In Fixed Model condition, bypass auto routing and target self.fixed_model_id directly
        target_model = self.fixed_model_id if self.fixed_model_id else "auto"
        req_id = f"TRACE_{condition_name}_{query_id}_{uuid.uuid4().hex[:6]}"

        request = InferenceRequest(
            request_id=req_id,
            task_type="qa",
            model_id=target_model,
            prompt_or_payload=synthesized.formatted_context,
            metadata={
                "query": cleaned_query,
                "doc_id": doc_id,
                "query_id": query_id,
                "condition": condition_name,
                "token_count": synthesized.token_count_estimate,
            },
        )

        inf_start = time.perf_counter()
        response: InferenceResponse = self.inference_pipeline.execute(request)
        inf_elapsed_ms = (time.perf_counter() - inf_start) * 1000.0

        raw_answer = str(response.result) if response.status == "SUCCESS" else f"Error: {response.error}"

        # 4. Citation Verification
        audit = self.verifier.verify_answer(raw_answer, passages)
        citations_output = audit.valid_citations
        if not citations_output and passages and audit.epistemic_status == "EVIDENCE_BACKED":
            top_p = passages[0]
            citations_output = [{
                "document": top_p.document_name,
                "page": top_p.page_number,
                "block_id": top_p.block_id,
                "bounding_box": top_p.bounding_box,
                "confidence": top_p.confidence,
            }]

        total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        resp_meta = response.metadata or {}
        pipe_tel = resp_meta.get("pipeline_telemetry", {})
        routing_dec = pipe_tel.get("routing_decision", {})
        sched_dec = pipe_tel.get("scheduling", {})

        worker_id = sched_dec.get("worker_id") or resp_meta.get("worker_id", "default_worker")
        executing_model = response.model_id or routing_dec.get("selected_model", target_model)

        ans = VerifiedAnswer(
            query=cleaned_query,
            answer_text=raw_answer,
            epistemic_status=audit.epistemic_status,
            citations=citations_output,
            grounding_score=audit.grounding_score,
            retrieved_passages=passages,
            executing_model_id=executing_model,
            execution_time_ms=round(total_elapsed_ms, 2),
            explanation="; ".join(audit.audit_notes) if audit.audit_notes else "Verified",
        )

        exec_time_ms = response.execution_time_ms
        queue_wait_ms = max(0.0, inf_elapsed_ms - exec_time_ms)

        telemetry = {
            "query_id": query_id,
            "correlation_id": req_id,
            "condition": condition_name,
            "routing_policy": "fixed" if self.fixed_model_id else "adaptive",
            "selected_model": executing_model,
            "selected_worker": worker_id,
            "queue_wait_ms": round(queue_wait_ms, 2),
            "execution_time_ms": round(exec_time_ms, 2),
            "retrieval_time_ms": round(retrieval_elapsed_ms, 2),
            "total_latency_ms": round(total_elapsed_ms, 2),
            "status": response.status,
            "epistemic_status": audit.epistemic_status,
            "http_status": 200 if response.status == "SUCCESS" else 503,
        }

        return ans, telemetry


def run_qa_quality_benchmark(
    condition_name: str,
    doc_pipeline: DocumentIntelligencePipeline,
    queries_path: str = "benchmarks/v1_1/queries/qa_evaluation_queries.json",
    scheduler_type: str = "ROUND_ROBIN",
    fixed_model_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Executes the 100-query benchmark under the designated condition."""
    queries_file = Path(queries_path)
    with open(queries_file, "r", encoding="utf-8") as f:
        query_set = json.load(f)

    # Initialize inference pipeline
    registry = get_model_registry()
    scheduler: BaseScheduler = (
        CapacityAwareScheduler() if scheduler_type == "CAPACITY_AWARE" else RoundRobinScheduler()
    )

    inf_pipeline = IntelligentInferencePipeline(
        registry=registry,
        scheduler=scheduler,
        auto_spawn_workers=True,
    )

    qa_engine = BenchmarkQAEngine(
        retriever=doc_pipeline.retriever,
        inference_pipeline=inf_pipeline,
        fixed_model_id=fixed_model_id,
    )

    raw_results: List[Dict[str, Any]] = []

    for q in query_set:
        qid = q["query_id"]
        qtext = q["question"]
        gold_ans = q["reference_answer"]
        expected_blocks = q.get("expected_block_ids", [])
        is_supported = q.get("is_supported", True)

        ans, trace = qa_engine.answer_question_benchmark(
            query=qtext,
            query_id=qid,
            condition_name=condition_name,
        )

        retrieved_block_ids = [p.block_id for p in ans.retrieved_passages]

        # Quality metrics
        em = compute_exact_match(ans.answer_text, gold_ans)
        prec, rec, f1 = compute_token_f1(ans.answer_text, gold_ans)
        cite_prec = compute_citation_precision(ans.citations, expected_blocks)
        ret_metrics = compute_retrieval_metrics(retrieved_block_ids, expected_blocks)

        record = {
            "query_id": qid,
            "condition": condition_name,
            "routing_policy": trace["routing_policy"],
            "selected_model": trace["selected_model"],
            "selected_worker": trace["selected_worker"],
            "queue_wait_ms": trace["queue_wait_ms"],
            "execution_time_ms": trace["execution_time_ms"],
            "total_latency_ms": trace["total_latency_ms"],
            "answer": ans.answer_text,
            "ground_truth_answer": gold_ans,
            "retrieved_block_ids": retrieved_block_ids,
            "relevant_block_ids": expected_blocks,
            "exact_match": em,
            "token_precision": round(prec, 4),
            "token_recall": round(rec, 4),
            "token_f1": round(f1, 4),
            "citation_precision": round(cite_prec, 4),
            "retrieval_metrics": ret_metrics,
            "epistemic_status": ans.epistemic_status,
            "expected_epistemic_status": q.get("expected_epistemic_status", "EVIDENCE_BACKED"),
            "is_supported": is_supported,
            "http_status": trace.get("http_status", 200),
            "status": trace.get("status", "SUCCESS"),
        }
        raw_results.append(record)

    # Clean up pipeline threads
    inf_pipeline.shutdown()

    # Aggregate metrics across the 100 queries
    em_list = [r["exact_match"] for r in raw_results]
    f1_list = [r["token_f1"] for r in raw_results]
    cp_list = [r["citation_precision"] for r in raw_results]
    rec3_list = [r["retrieval_metrics"]["recall@3"] for r in raw_results]
    ndcg3_list = [r["retrieval_metrics"]["ndcg@3"] for r in raw_results]
    mrr_list = [r["retrieval_metrics"]["mrr"] for r in raw_results]
    lat_list = [r["total_latency_ms"] for r in raw_results]

    lat_percentiles = compute_percentiles_with_ci(lat_list, percentiles=(50.0, 95.0, 99.0))

    summary = {
        "condition": condition_name,
        "total_queries": len(raw_results),
        "routing_policy": "fixed" if fixed_model_id else "adaptive",
        "scheduler_type": scheduler_type,
        "mean_exact_match": round(float(np.mean(em_list)), 4),
        "mean_token_f1": round(float(np.mean(f1_list)), 4),
        "mean_citation_precision": round(float(np.mean(cp_list)), 4),
        "mean_retrieval_recall_at_3": round(float(np.mean(rec3_list)), 4),
        "mean_ndcg_at_3": round(float(np.mean(ndcg3_list)), 4),
        "mean_mrr": round(float(np.mean(mrr_list)), 4),
        "mean_total_latency_ms": round(float(np.mean(lat_list)), 2),
        "latency_percentiles_ms": lat_percentiles,
        "rejection_rate": round(sum(1 for r in raw_results if r["status"] == "REJECTED") / len(raw_results), 4),
    }

    return raw_results, summary
