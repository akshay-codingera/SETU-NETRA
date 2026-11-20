"""
qa_runner.py: Grounded Document Question Answering and Citation verification evaluation runner.

Why this file exists:
Evaluates the end-to-end evidence retrieval, extractive QA, and citation verification
pipeline on real ingested documents in the repository (output/e2e_verify/e2e_netra.db):
1. Retrieval relevance: Recall@K, Precision@K, Mean Reciprocal Rank (MRR)
2. Answer correctness: Exact Match (EM) and Token F1
3. Citation precision & completeness (verifying cited page and block IDs exist and match)
4. Unsupported query rejection (epistemic abstention for queries without evidence)
5. Hallucination detection
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.core.contracts import RetrievedPassage
from setu_netra.qa.engine import EvidenceGroundedQAEngine
from setu_netra.qa.verifier import CitationVerifier
from setu_netra.retrieval.document_retriever import DocumentRetriever
from setu_netra.routing.adapters.grounded_qa_adapter import GroundedExtractiveQAAdapter
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine
from setu_netra.semantic.embeddings.offline_engine import OfflineSemanticEngine
from setu_netra.store.sqlite_store import SQLiteDocumentStore

from benchmarks.experiments.experiment_tracker import ExperimentMetadata, ExperimentTracker
from benchmarks.metrics.calculator import (
    compute_citation_metrics,
    compute_qa_token_f1_and_em,
    compute_retrieval_ranking_metrics,
    compute_statistical_summary,
)

logger = logging.getLogger(__name__)


class DocumentQAEvaluationRunner:
    """Evaluates retrieval quality, answer correctness, citation precision, and epistemic abstention."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        dataset_path: Optional[Path] = None,
        tracker: Optional[ExperimentTracker] = None,
    ):
        self._repo_root = Path(__file__).resolve().parent.parent.parent
        self._db_path = db_path or (self._repo_root / "output" / "e2e_verify" / "e2e_netra.db")
        self._dataset_path = dataset_path or (self._repo_root / "benchmarks" / "datasets" / "qa_eval_dataset.json")
        self._tracker = tracker or ExperimentTracker()

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(self._dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def setup_qa_engine(self) -> Tuple[EvidenceGroundedQAEngine, DocumentRetriever]:
        store = SQLiteDocumentStore(self._db_path)
        # Use sentence transformers or offline engine
        try:
            embed_engine = NeuralSentenceEmbeddingEngine()
        except Exception:
            embed_engine = OfflineSemanticEngine()

        retriever = DocumentRetriever(store=store, embedding_engine=embed_engine)
        qa_adapter = GroundedExtractiveQAAdapter(model_id="grounded-extractive-qa-v1")
        qa_engine = EvidenceGroundedQAEngine(retriever=retriever, model_adapter=qa_adapter)
        return qa_engine, retriever

    def execute_qa_evaluation(self) -> Dict[str, Any]:
        """Execute evaluation over labeled QA dataset against genuine SQLite store."""
        print("=" * 80)
        print("STAGE 6: DOCUMENT QA QUALITY & CITATION EVALUATION")
        print(f"Target Database: {self._db_path.name}")
        print("=" * 80)

        qa_engine, retriever = self.setup_qa_engine()
        dataset = self.load_dataset()

        retrieved_ids_list: List[List[str]] = []
        relevant_ids_list: List[Set[str]] = []

        exact_match_scores: List[float] = []
        token_f1_scores: List[float] = []
        citation_precisions: List[float] = []
        citation_completenesses: List[float] = []

        supported_count = 0
        unsupported_count = 0
        unsupported_correctly_rejected = 0
        hallucination_detected_count = 0

        raw_eval_records: List[Dict[str, Any]] = []

        for item in dataset:
            q_id = item["id"]
            question = item["question"]
            gold_answer = item["reference_answer"]
            is_supported = item.get("is_supported", True)
            target_doc = item.get("document_id")

            # 1. Retrieval Evaluation
            passages: List[RetrievedPassage] = retriever.retrieve(query=question, top_k=5)
            retrieved_doc_ids = [p.doc_id for p in passages]
            retrieved_ids_list.append(retrieved_doc_ids)

            relevant_set: Set[str] = {target_doc} if target_doc else set()
            relevant_ids_list.append(relevant_set)

            # 2. Answer Generation & Citation Extraction
            t0 = time.perf_counter()
            qa_res = qa_engine.answer_question(query=question, top_k=3)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            predicted_answer = qa_res.answer_text
            epistemic_status = qa_res.epistemic_status
            citations = qa_res.citations

            # Check for abstention
            is_abstention = (
                "not contain sufficient verified evidence" in predicted_answer.lower()
                or epistemic_status == "UNSUPPORTED"
            )

            # 3. Calculate Correctness & Citations
            if is_supported:
                supported_count += 1
                em, f1 = compute_qa_token_f1_and_em(predicted_answer, gold_answer)
                exact_match_scores.append(em)
                token_f1_scores.append(f1)

                # Citation check
                expected_citations = []
                if target_doc and item.get("page_number"):
                    expected_citations.append({
                        "doc_id": target_doc,
                        "page_number": item["page_number"],
                        "block_id": item.get("block_id"),
                    })

                cite_stats = compute_citation_metrics(citations, expected_citations)
                citation_precisions.append(cite_stats["citation_precision"])
                citation_completenesses.append(cite_stats["citation_completeness"])

                # Hallucination indicator: answer text has zero token overlap with retrieved passages
                retrieved_corpus = " ".join(p.text for p in passages).lower()
                answer_tokens = set(predicted_answer.lower().split())
                if answer_tokens and not any(tok in retrieved_corpus for tok in answer_tokens if len(tok) > 3):
                    hallucination_detected_count += 1
            else:
                unsupported_count += 1
                if is_abstention:
                    unsupported_correctly_rejected += 1
                exact_match_scores.append(1.0 if is_abstention else 0.0)
                token_f1_scores.append(1.0 if is_abstention else 0.0)
                citation_precisions.append(1.0 if not citations else 0.0)
                citation_completenesses.append(1.0)

            raw_eval_records.append({
                "id": q_id,
                "question": question,
                "gold_answer": gold_answer,
                "predicted_answer": predicted_answer,
                "epistemic_status": epistemic_status,
                "is_supported": is_supported,
                "is_abstention": is_abstention,
                "exact_match": exact_match_scores[-1],
                "token_f1": token_f1_scores[-1],
                "citation_precision": citation_precisions[-1],
                "citation_completeness": citation_completenesses[-1],
                "retrieved_doc_ids": retrieved_doc_ids,
                "citations": citations,
                "latency_ms": round(elapsed_ms, 2),
            })

        # 4. Aggregate Metrics
        ranking_metrics = compute_retrieval_ranking_metrics(retrieved_ids_list, relevant_ids_list)
        em_summary = compute_statistical_summary(exact_match_scores)
        f1_summary = compute_statistical_summary(token_f1_scores)
        cite_prec_summary = compute_statistical_summary(citation_precisions)
        cite_comp_summary = compute_statistical_summary(citation_completenesses)

        unsupported_abstention_rate = (
            (unsupported_correctly_rejected / unsupported_count) if unsupported_count > 0 else 1.0
        )
        hallucination_rate = (
            (hallucination_detected_count / supported_count) if supported_count > 0 else 0.0
        )

        aggregated = {
            "total_questions_evaluated": len(dataset),
            "supported_questions": supported_count,
            "unsupported_questions": unsupported_count,
            "retrieval_ranking": ranking_metrics,
            "exact_match": em_summary,
            "token_f1": f1_summary,
            "citation_precision": cite_prec_summary,
            "citation_completeness": cite_comp_summary,
            "unsupported_abstention_accuracy": round(unsupported_abstention_rate * 100.0, 2),
            "hallucination_rate_percent": round(hallucination_rate * 100.0, 2),
        }

        print(f"Retrieval MRR:                  {ranking_metrics['mrr']:.4f}")
        print(f"Retrieval Recall@1:             {ranking_metrics.get('recall@1', 0.0):.4f}")
        print(f"Retrieval Recall@3:             {ranking_metrics.get('recall@3', 0.0):.4f}")
        print(f"Mean Token F1:                  {f1_summary['mean']:.4f}")
        print(f"Exact Match Mean:               {em_summary['mean'] * 100:.1f}%")
        print(f"Citation Precision:             {cite_prec_summary['mean'] * 100:.1f}%")
        print(f"Citation Completeness:          {cite_comp_summary['mean'] * 100:.1f}%")
        print(f"Unsupported Abstention Rate:    {unsupported_abstention_rate * 100:.1f}%")
        print(f"Hallucination Rate:             {hallucination_rate * 100:.1f}%")

        metadata = ExperimentMetadata(
            experiment_id="qa_quality_evaluation",
            suite_name="Stage 6 Document QA Quality Evaluation",
            description="Empirical evaluation of retrieval ranking, answer correctness, citation precision, and epistemic abstention.",
            workload_id="real_doc_eval_set",
            total_requests=len(dataset),
        )

        raw_path = self._tracker.save_raw_experiment_data("qa_quality_evaluation", metadata, raw_eval_records)
        summary_path = self._tracker.save_aggregated_results("qa_quality_evaluation", metadata, aggregated)
        print(f"\n[OK] QA Quality evaluation completed.")
        print(f"  Raw records saved:         {raw_path}")
        print(f"  Aggregated results saved:  {summary_path}")

        return aggregated
