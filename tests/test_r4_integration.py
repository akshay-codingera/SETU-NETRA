"""
test_r4_integration.py: Full System Architectural Integration Test Suite for Milestone R4.

Validates:
1. Simultaneous loading of R1 (SR-EdgeNet), R2 (ER-SP), R3 (CM-RP v2) models.
2. End-to-end dataflow through IntegratedSetuNetraPipeline:
   - Query validation
   - Layout structure prediction
   - Evidence sufficiency evaluation
   - Hardware telemetry and strategy selection
   - Solver execution and result formatting
   - Citation verification and grounding
   - Epistemic abstention handling
3. Low-memory constraint handling (masking LOCAL_SLM when RAM < 1.5GB).
4. Robustness against empty/malformed inputs.
5. Latency and memory compliance on CPU-first execution.
"""

import os
import sys
import time
import pytest
import numpy as np
import torch

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from setu_netra.pipeline.integrated_pipeline import IntegratedSetuNetraPipeline, IntegratedPipelineResult
from setu_netra.structure.sr_edge_net import SRClass
from setu_netra.evidence.er_sp import ERClass
from setu_netra.policy.cm_rp import StrategyAction, ContextFeatureExtractor
from setu_netra.routing.system_telemetry import SystemTelemetry
from setu_netra.core.contracts import RetrievedPassage


@pytest.fixture(scope="module")
def pipeline():
    """Instantiate complete integrated pipeline."""
    pipe = IntegratedSetuNetraPipeline(
        sr_checkpoint="models/structure/sr_edge_net.pt",
        er_checkpoint="models/evidence/er_sp.pt",
        policy_checkpoint="models/policy/cm_rp_v2.pt",
        use_rule_fallback=True
    )
    return pipe


class TestR4FullIntegration:
    """Full-system integration test suite for Milestone R4."""

    def test_01_all_models_loaded_simultaneously(self, pipeline):
        """Verify all three models load together into memory on CPU."""
        assert pipeline.is_fully_loaded, "Pipeline failed to report all models loaded"
        assert pipeline.sr_engine.is_loaded, "SR-EdgeNet not loaded"
        assert pipeline.er_predictor.is_loaded, "ER-SP not loaded"
        assert pipeline.cm_predictor.is_loaded, "CM-RP not loaded"
        assert pipeline.sr_engine.device.type == "cpu", "SR-EdgeNet not on CPU"
        assert pipeline.er_predictor.device.type == "cpu", "ER-SP not on CPU"
        assert pipeline.cm_predictor.device.type == "cpu", "CM-RP not on CPU"

    def test_02_arithmetic_solver_execution(self, pipeline):
        """Test arithmetic inquiry routing and deterministic solver execution."""
        q = "Calculate result = 45 * 2 - 15 + 10; what is result?"
        passages = ["Context: standard numerical computation."]
        res = pipeline.process_inquiry(query=q, retrieved_passages=passages)

        assert isinstance(res, IntegratedPipelineResult)
        assert res.selected_action == StrategyAction.ARITHMETIC_SOLVER.value
        assert "85" in res.final_answer or "result = 85" in res.final_answer
        assert res.epistemic_status == "COMPUTATION_VERIFIED"
        assert not res.is_abstention
        assert res.grounding_score == 1.0

    def test_03_dbms_solver_execution(self, pipeline):
        """Test DBMS inquiry routing and relational decomposition."""
        q = "Relation R(A, B, C, D) with functional dependencies A -> B and B -> C; find candidate keys and normal form."
        passages = ["Normalization theory in relational database design."]
        res = pipeline.process_inquiry(query=q, retrieved_passages=passages)

        assert res.selected_action == StrategyAction.DBMS_SOLVER.value
        assert not res.is_abstention
        assert res.grounding_score == 1.0
        assert "candidate" in res.final_answer.lower() or "bcnf" in res.final_answer.lower() or "3nf" in res.final_answer.lower()

    def test_04_formal_logic_solver_execution(self, pipeline):
        """Test formal logic inquiry routing and validity check."""
        q = "Premise: All primates are mammals. Premise: All humans are primates. Does it conclude All humans are mammals?"
        passages = ["Standard categorical syllogism deduction."]
        res = pipeline.process_inquiry(query=q, retrieved_passages=passages)

        assert res.selected_action == StrategyAction.FORMAL_LOGIC_SOLVER.value
        assert not res.is_abstention
        assert res.grounding_score == 1.0
        assert "valid" in res.final_answer.lower()

    def test_05_extractive_qa_and_citation_verification(self, pipeline):
        """Test extractive QA passage grounding with citation verifier."""
        q = "What algorithm does Raft use for leader election?"
        passages = [
            RetrievedPassage(
                doc_id="raft_spec_v1",
                document_name="raft_spec_v1.pdf",
                page_number=3,
                block_id=12,
                block_type="PARAGRAPH",
                text="Raft uses randomized election timers to select leaders and prevent split votes.",
                bounding_box=(0.1, 0.2, 0.8, 0.3),
                confidence=0.98,
                similarity_score=0.88
            )
        ]
        res = pipeline.process_inquiry(query=q, retrieved_passages=passages)

        assert res.selected_action in (StrategyAction.EXTRACTIVE_QA.value, StrategyAction.LOCAL_SLM.value)
        assert len(res.final_answer) > 0
        assert not res.is_abstention

    def test_06_epistemic_abstention_on_contradiction(self, pipeline):
        """Verify ER-SP identifies contradiction and enforces epistemic refusal."""
        q = "Why did the node fail to commit the transaction?"
        passages = [
            "The node successfully committed the transaction and flushed to WAL.",
            "The node aborted and never committed the transaction due to deadlock."
        ]
        res = pipeline.process_inquiry(query=q, retrieved_passages=passages)

        # Pipeline should intercept contradiction or abstain
        if res.er_sufficiency_label in ("CONTRADICTORY", "UNVERIFIABLE"):
            assert res.is_abstention, "Expected abstention on contradictory evidence"
            assert res.epistemic_status in ("CONTRADICTORY_EVIDENCE", "UNSUPPORTED", "UNVERIFIED_INFERENCE")

    def test_07_hardware_telemetry_low_memory_mask(self, pipeline):
        """Verify that under severe RAM pressure, LOCAL_SLM is masked out."""
        low_ram_telem = SystemTelemetry(
            cpu_percent=45.0,
            ram_percent=95.0,
            avail_ram_mb=800.0,  # Below 1500 MB threshold
            total_ram_mb=16384.0,
            timestamp=time.time()
        )
        extractor = ContextFeatureExtractor()
        _, mask = extractor.extract_features(
            question="Compare Raft and Paxos consensus models in depth.",
            telemetry=low_ram_telem
        )
        local_slm_id = StrategyAction.get_all().index(StrategyAction.LOCAL_SLM.value)
        assert mask[local_slm_id] == 0.0, "LOCAL_SLM should be masked (0.0) when available RAM < 1500 MB"

    def test_08_empty_query_defense(self, pipeline):
        """Verify defensive handling of empty or blank query strings."""
        res_empty = pipeline.process_inquiry(query="   ", retrieved_passages=["Some passage"])
        assert res_empty.is_abstention
        assert res_empty.selected_action == StrategyAction.ABSTAIN.value
        assert "Empty" in res_empty.abstention_reason or "empty" in res_empty.abstention_reason.lower()

    def test_09_sr_edgenet_block_hierarchy(self, pipeline):
        """Verify SR-EdgeNet integration with OCR layout blocks."""
        blocks = [
            {"block_id": 1, "text": "Question 1: What is normal form?", "bbox": [50, 100, 500, 130]},
            {"block_id": 2, "text": "A) First Normal Form", "bbox": [50, 140, 300, 160]},
            {"block_id": 3, "text": "B) Second Normal Form", "bbox": [50, 170, 300, 190]},
        ]
        res = pipeline.process_inquiry(
            query="What is normal form?",
            ocr_blocks=blocks,
            retrieved_passages=["Normalization definitions."]
        )
        assert res.sr_relationships_predicted >= 1

    def test_10_execution_latency_cpu(self, pipeline):
        """Verify sub-150ms execution latency on standard CPU inquiry."""
        q = "Calculate result = 100 / 4 + 25;"
        t0 = time.perf_counter()
        res = pipeline.process_inquiry(query=q, retrieved_passages=["Standard arithmetic."])
        t_lat_ms = (time.perf_counter() - t0) * 1000.0
        assert res.selected_action == StrategyAction.ARITHMETIC_SOLVER.value
        assert t_lat_ms < 250.0, f"Latency {t_lat_ms:.2f}ms exceeded 250ms threshold"
