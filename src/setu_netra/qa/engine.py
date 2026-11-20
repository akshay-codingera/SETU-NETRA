"""
engine.py: Evidence-Grounded Question Answering Engine for SETU-NETRA.

Why this file exists:
Coordinates query understanding, hybrid retrieval, token-budgeted context synthesis,
unified model inference, citation verification, and epistemic categorization into a single,
production-grade question-answering workflow.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from setu_netra.context.synthesizer import EvidenceContextSynthesizer
from setu_netra.core.contracts import RetrievedPassage
from setu_netra.qa.question_extractor import classify_question_intent
from setu_netra.qa.verifier import CitationVerificationResult, CitationVerifier
from setu_netra.retrieval.document_retriever import DocumentRetriever
from setu_netra.routing.contracts import InferenceRequest, InferenceResponse
from setu_netra.routing.interfaces import BaseModelAdapter
from setu_netra.routing.registry import get_model_registry
from setu_netra.store.sqlite_store import SQLiteDocumentStore


@dataclass
class VerifiedAnswer:
    """The final verified output returned from the Evidence-Grounded QA Engine."""
    query: str
    answer_text: str
    epistemic_status: str              # 'EVIDENCE_BACKED' | 'GENERAL_KNOWLEDGE' | 'UNSUPPORTED' | 'COMPUTATION_VERIFIED' | 'LOGIC_VERIFIED'
    citations: List[Dict[str, Any]]
    grounding_score: float
    retrieved_passages: List[RetrievedPassage]
    executing_model_id: str
    execution_time_ms: float
    explanation: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    domain: str = "DOCUMENT_QA"
    reconstructed_question: Optional[str] = None
    verification_method: Optional[str] = None
    step_by_step_explanation: Optional[str] = None


class EvidenceGroundedQAEngine:
    """Production question answering engine grounded in retrieved document evidence."""

    def __init__(
        self,
        retriever: DocumentRetriever,
        model_adapter: Optional[BaseModelAdapter] = None,
        synthesizer: Optional[EvidenceContextSynthesizer] = None,
        verifier: Optional[CitationVerifier] = None,
        inference_pipeline: Optional[Any] = None,
    ):
        self.retriever = retriever
        self.synthesizer = synthesizer or EvidenceContextSynthesizer(default_budget_tokens=1500)
        self.verifier = verifier or CitationVerifier(min_overlap_threshold=0.30)
        self.inference_pipeline = inference_pipeline

        # Default model adapter from registry if not provided
        if model_adapter is None:
            registry = get_model_registry()
            self.model_adapter = registry.get_default_for_task("qa")
            if self.model_adapter is None:
                from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
                self.model_adapter = GroundedExtractiveQAAdapter()
        else:
            self.model_adapter = model_adapter

    def answer_question(
        self,
        query: str,
        doc_id: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.20,
        max_budget_tokens: int = 1500,
        alpha: float = 0.70,
        model_id: Optional[str] = None,
        think: Optional[bool] = None,
        workspace_id: Optional[str] = None,
    ) -> VerifiedAnswer:
        """Execute end-to-end evidence-grounded question answering for a query.

        Args:
            query: User question or inquiry string.
            doc_id: Optional document ID filter (e.g. active document).
            top_k: Number of evidence passages to retrieve.
            threshold: Minimum hybrid retrieval similarity threshold.
            max_budget_tokens: Context window token limit.
            alpha: Hybrid retrieval weight (dense vs lexical).
            model_id: Optional model ID override (e.g. 'qwen3.5:2b' or 'auto').
            think: Optional boolean to enable/disable reasoning think mode.
            workspace_id: Optional workspace ID filter for multi-tenant isolation.

        Returns:
            VerifiedAnswer containing the grounded answer, citations, and status.
        """
        start_time = time.perf_counter()
        cleaned_query = query.strip()

        # Handle empty query defensively
        if not cleaned_query:
            return VerifiedAnswer(
                query="",
                answer_text="Empty query provided. Please ask a specific question about the document.",
                epistemic_status="UNSUPPORTED",
                citations=[],
                grounding_score=0.0,
                retrieved_passages=[],
                executing_model_id=self.model_adapter.model_id,
                execution_time_ms=0.0,
                explanation="No query terms provided.",
            )

        # 1. Query Understanding & Domain Pre-Classification
        intent = classify_question_intent(cleaned_query, is_mcq=False)
        from setu_netra.qa.domain_router import (
            DomainSolverRouter,
            QuestionDomain,
            classify_domain,
            normalize_ocr_arithmetic_tokens,
        )

        direct_domain, direct_conf, direct_meta = classify_domain(cleaned_query)
        if direct_domain in (QuestionDomain.ARITHMETIC, QuestionDomain.PROGRAMMING):
            arith_res = DomainSolverRouter.solve_arithmetic_inquiry(cleaned_query)
            if arith_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=arith_res.final_answer,
                    epistemic_status=str(arith_res.epistemic_status.value),
                    citations=[],
                    grounding_score=1.0,
                    retrieved_passages=[],
                    executing_model_id="deterministic_ast_evaluator",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=arith_res.step_by_step_explanation,
                    domain="ARITHMETIC",
                    reconstructed_question=arith_res.reconstructed_question,
                    verification_method="DETERMINISTIC_AST_EVALUATION",
                    step_by_step_explanation=arith_res.step_by_step_explanation,
                    metadata={"domain": "ARITHMETIC", "confidence": arith_res.confidence},
                )

        if direct_domain == QuestionDomain.DBMS_NORMALIZATION:
            dbms_res = DomainSolverRouter.solve_dbms_normalization_inquiry(cleaned_query)
            if dbms_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=dbms_res.final_answer,
                    epistemic_status=str(dbms_res.epistemic_status.value),
                    citations=[],
                    grounding_score=1.0,
                    retrieved_passages=[],
                    executing_model_id="relational_closure_normal_form_engine",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=dbms_res.step_by_step_explanation,
                    domain="DBMS_NORMALIZATION",
                    reconstructed_question=dbms_res.reconstructed_question,
                    verification_method="RELATIONAL_CLOSURE_AND_NORMAL_FORM_ALGORITHM",
                    step_by_step_explanation=dbms_res.step_by_step_explanation,
                    metadata={
                        "domain": "DBMS_NORMALIZATION",
                        "confidence": dbms_res.confidence,
                        "selected_option": dbms_res.selected_option,
                        "candidate_keys": dbms_res.metadata.get("candidate_keys", []),
                        "highest_normal_form": dbms_res.metadata.get("highest_normal_form", ""),
                        "option_analysis": dbms_res.metadata.get("option_analysis", {}),
                    },
                )

        if direct_domain in (QuestionDomain.CRYPTOGRAPHY,):
            crypto_res = DomainSolverRouter.solve_cryptography_inquiry(cleaned_query)
            if crypto_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=crypto_res.final_answer,
                    epistemic_status=str(crypto_res.epistemic_status.value),
                    citations=[],
                    grounding_score=1.0,
                    retrieved_passages=[],
                    executing_model_id="cryptographic_math_engine",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=crypto_res.step_by_step_explanation,
                    domain="CRYPTOGRAPHY",
                    reconstructed_question=crypto_res.reconstructed_question,
                    verification_method=crypto_res.verification_method,
                    step_by_step_explanation=crypto_res.step_by_step_explanation,
                    metadata={"domain": "CRYPTOGRAPHY", "confidence": crypto_res.confidence},
                )

        if direct_domain in (QuestionDomain.MATHEMATICS,):
            math_res = DomainSolverRouter.solve_mathematics_inquiry(cleaned_query)
            if math_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=math_res.final_answer,
                    epistemic_status=str(math_res.epistemic_status.value),
                    citations=[],
                    grounding_score=1.0,
                    retrieved_passages=[],
                    executing_model_id="deterministic_math_engine",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=math_res.step_by_step_explanation,
                    domain="MATHEMATICS",
                    reconstructed_question=math_res.reconstructed_question,
                    verification_method=math_res.verification_method,
                    step_by_step_explanation=math_res.step_by_step_explanation,
                    metadata={"domain": "MATHEMATICS", "confidence": math_res.confidence},
                )

        if direct_domain == QuestionDomain.SQL:
            sql_res = DomainSolverRouter.solve_sql_inquiry(cleaned_query)
            if sql_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=sql_res.final_answer,
                    epistemic_status=str(sql_res.epistemic_status.value),
                    citations=[],
                    grounding_score=0.0,
                    retrieved_passages=[],
                    executing_model_id="relational_algebra_engine",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=sql_res.step_by_step_explanation,
                    domain="SQL",
                    reconstructed_question=sql_res.reconstructed_question,
                    verification_method="RELATIONAL_ALGEBRA_EVALUATION",
                    step_by_step_explanation=sql_res.step_by_step_explanation,
                    metadata={
                        "domain": "SQL",
                        "confidence": sql_res.confidence,
                        "selected_option": sql_res.selected_option,
                        "option_analysis": sql_res.metadata.get("option_analysis", {}),
                    },
                )

        if direct_domain == QuestionDomain.LOGICAL_REASONING:
            logic_res = DomainSolverRouter.solve_logical_reasoning_inquiry(cleaned_query)
            if logic_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=logic_res.final_answer,
                    epistemic_status=str(logic_res.epistemic_status.value),
                    citations=[],
                    grounding_score=0.0,
                    retrieved_passages=[],
                    executing_model_id="countermodel_syllogism_prover",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=logic_res.step_by_step_explanation,
                    domain="LOGICAL_REASONING",
                    reconstructed_question=logic_res.reconstructed_question,
                    verification_method="FORMAL_SET_THEORETIC_COUNTERMODEL",
                    step_by_step_explanation=logic_res.step_by_step_explanation,
                    metadata={
                        "domain": "LOGICAL_REASONING",
                        "confidence": logic_res.confidence,
                        "selected_option": logic_res.selected_option,
                        "option_analysis": logic_res.metadata.get("option_analysis", {}),
                    },
                )

        # 2. Hybrid Document Retrieval
        passages = self.retriever.retrieve(
            query=cleaned_query,
            top_k=top_k,
            threshold=threshold,
            doc_id=doc_id,
            alpha=alpha,
            suppress_duplicates=True,
            workspace_id=workspace_id,
        )

        # 3. Check for retrieval absence / insufficient evidence
        if not passages:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            if direct_domain == QuestionDomain.GENERAL_KNOWLEDGE and self.inference_pipeline:
                # Open-domain fallback for general knowledge inquiries
                req = InferenceRequest(
                    task_type="qa",
                    model_id=model_id or "auto",
                    prompt_or_payload=f"Answer the following question clearly:\n{cleaned_query}",
                    metadata={"intent": intent, "domain": "GENERAL_KNOWLEDGE"},
                    timeout=45.0,
                )
                resp = self.inference_pipeline.execute(req)
                gk_answer = str(getattr(resp, "result", None) or getattr(resp, "error", "") or "")
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=gk_answer,
                    epistemic_status="GENERAL_KNOWLEDGE",
                    citations=[],
                    grounding_score=0.0,
                    retrieved_passages=[],
                    executing_model_id=resp.model_id or "auto",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation="Answer derived from general model knowledge; not grounded in corpus documents.",
                    domain="GENERAL_KNOWLEDGE",
                    reconstructed_question=cleaned_query,
                    verification_method="MODEL_KNOWLEDGE_DISCLOSURE",
                    step_by_step_explanation="Answer derived from internal parameter knowledge without document citation.",
                    metadata={"intent": intent, "domain": "GENERAL_KNOWLEDGE"},
                )

            return VerifiedAnswer(
                query=cleaned_query,
                answer_text="The uploaded document does not contain sufficient verified evidence to answer this question.",
                epistemic_status="UNSUPPORTED",
                citations=[],
                grounding_score=0.0,
                retrieved_passages=[],
                executing_model_id=self.model_adapter.model_id,
                execution_time_ms=round(elapsed_ms, 2),
                explanation="No passages passed the hybrid relevance threshold.",
                domain="DOCUMENT_QA",
                reconstructed_question=cleaned_query,
                verification_method="RETRIEVAL_THRESHOLD_CHECK",
                step_by_step_explanation="No context passages met minimum similarity threshold.",
                metadata={"intent": intent},
            )

        # 4. Check if retrieved context contains a self-contained arithmetic or SQL problem
        ctx_domain, ctx_conf, ctx_meta = classify_domain(cleaned_query, context_text=passages[0].text)
        if ctx_domain == QuestionDomain.ARITHMETIC:
            arith_res = DomainSolverRouter.solve_arithmetic_inquiry(
                passages[0].text,
                source_doc_name=passages[0].document_name,
            )
            if arith_res.is_direct_solvable:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerifiedAnswer(
                    query=cleaned_query,
                    answer_text=arith_res.final_answer,
                    epistemic_status=str(arith_res.epistemic_status.value),
                    citations=[],  # Never fabricate citations for arithmetic calculations
                    grounding_score=1.0,
                    retrieved_passages=passages,
                    executing_model_id="deterministic_ast_evaluator",
                    execution_time_ms=round(elapsed_ms, 2),
                    explanation=arith_res.step_by_step_explanation,
                    domain="ARITHMETIC",
                    reconstructed_question=arith_res.reconstructed_question,
                    verification_method="DETERMINISTIC_AST_EVALUATION",
                    step_by_step_explanation=arith_res.step_by_step_explanation,
                    metadata={
                        "provenance_document": passages[0].document_name,
                        "domain": "ARITHMETIC",
                        "intent": intent,
                        "confidence": arith_res.confidence,
                    },
                )

        # 5. Token-Budgeted Context Synthesis
        synthesized = self.synthesizer.synthesize(
            query=cleaned_query,
            passages=passages,
            max_budget_tokens=max_budget_tokens,
        )

        # 5. Model Inference Execution via Unified Interface or Adaptive Pipeline
        req_model_id = model_id or ("auto" if self.inference_pipeline is not None else self.model_adapter.model_id)
        req_meta: Dict[str, Any] = {
            "query": cleaned_query,
            "doc_id": doc_id,
            "intent": intent,
            "token_count": synthesized.token_count_estimate,
        }
        if think is not None:
            req_meta["think"] = think

        timeout = 90.0 if ("ollama" in req_model_id.lower() or req_model_id == "auto") else 45.0
        request = InferenceRequest(
            task_type="qa",
            model_id=req_model_id,
            prompt_or_payload=synthesized.formatted_context,
            metadata=req_meta,
            timeout=timeout,
        )

        if self.inference_pipeline is not None:
            response: InferenceResponse = self.inference_pipeline.execute(request)
        else:
            response: InferenceResponse = self.model_adapter.execute(request)

        raw_answer = str(response.result) if response.status == "SUCCESS" else (
            f"Error during model execution: {response.error}"
        )

        # 6. Citation & Factuality Verification
        audit: CitationVerificationResult = self.verifier.verify_answer(raw_answer, passages)

        # Fallback formatting if model generated citations
        citations_output = audit.valid_citations
        if not citations_output and passages and audit.epistemic_status == "EVIDENCE_BACKED":
            # If answer was grounded in top passage
            top_p = passages[0]
            citations_output = [{
                "document": top_p.document_name,
                "page": top_p.page_number,
                "block_id": top_p.block_id,
                "bounding_box": top_p.bounding_box,
                "confidence": top_p.confidence,
            }]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        explanation = "; ".join(audit.audit_notes) if audit.audit_notes else "Answer verified against context passages."

        # Extract worker and telemetry metadata
        resp_meta = response.metadata or {}
        worker_id = resp_meta.get("worker_id") or resp_meta.get("scheduling", {}).get("worker_id", "default_worker")

        return VerifiedAnswer(
            query=cleaned_query,
            answer_text=raw_answer,
            epistemic_status=audit.epistemic_status,
            citations=citations_output,
            grounding_score=audit.grounding_score,
            retrieved_passages=passages,
            executing_model_id=response.model_id or getattr(response, "executing_model_id", self.model_adapter.model_id),
            execution_time_ms=round(elapsed_ms, 2),
            explanation=explanation,
            domain="DOCUMENT_QA",
            reconstructed_question=cleaned_query,
            verification_method="CITATION_GROUNDING_AUDIT",
            step_by_step_explanation=explanation,
            metadata={
                "intent": intent,
                "token_count": synthesized.token_count_estimate,
                "truncated": synthesized.truncated,
                "request_id": response.request_id,
                "worker_id": worker_id,
                "pipeline_telemetry": resp_meta.get("pipeline_telemetry", {}),
                "routing_decision": resp_meta.get("routing_decision", {}),
            },
        )
