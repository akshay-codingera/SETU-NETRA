"""
engine.py: Primary orchestrator for Semantic Understanding and Domain Classification (Module 4).

Why this file exists:
Coordinates text provenance extraction, context preparation, dense embeddings, concept extraction,
question intent classification, polysemous disambiguation, open-vocabulary domain classification,
and local knowledge retrieval into a unified, CPU-friendly pipeline.
"""

import time
from typing import List, Optional, Sequence
from setu_netra.core.contracts import (
    BlockType,
    DocumentBlock,
    DocumentStructureResult,
    QuestionGroup,
    SemanticAnalysisResult,
    SemanticItemAnalysis,
)
from setu_netra.semantic.analysis.concept_extractor import extract_concepts_and_entities
from setu_netra.semantic.analysis.intent_classifier import classify_question_intents
from setu_netra.semantic.analysis.technical_level import estimate_technical_level
from setu_netra.semantic.domain.classifier import OpenVocabularyDomainClassifier
from setu_netra.semantic.domain.disambiguation import disambiguate_terms
from setu_netra.semantic.domain.taxonomy import DomainTaxonomy
from setu_netra.semantic.embeddings.base import BaseEmbeddingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.semantic.retrieval.local_knowledge import LocalKnowledgeRetriever


class SemanticUnderstandingEngine:
    """Context-aware semantic understanding and open-vocabulary domain analysis engine."""

    def __init__(
        self,
        embedding_engine: Optional[BaseEmbeddingEngine] = None,
        taxonomy: Optional[DomainTaxonomy] = None,
        enable_retrieval: bool = True,
        abstention_threshold: Optional[float] = None,
    ):
        self._embedding_engine = embedding_engine or get_embedding_engine("auto")
        self._taxonomy = taxonomy or DomainTaxonomy()
        self._domain_classifier = OpenVocabularyDomainClassifier(
            embedding_engine=self._embedding_engine,
            taxonomy=self._taxonomy,
            abstention_threshold=abstention_threshold,
        )
        self._retriever = LocalKnowledgeRetriever(self._embedding_engine) if enable_retrieval else None

    @property
    def embedding_engine_name(self) -> str:
        return self._embedding_engine.engine_name

    def analyze_document_structure(
        self,
        structure_result: DocumentStructureResult,
        document_id: str = "document-1",
    ) -> SemanticAnalysisResult:
        """Execute semantic analysis on reconstructed document structure (Module 3 output).

        Args:
            structure_result: Reconstructed document structure from Module 3.
            document_id: Optional document identifier for provenance tracking.

        Returns:
            SemanticAnalysisResult containing structured semantic analyses.
        """
        start_time = time.perf_counter()
        items: List[SemanticItemAnalysis] = []
        doc_warnings: List[str] = list(structure_result.warnings)

        # Build ambient document context (e.g. headings or note blocks)
        context_snippets = [
            b.text for b in structure_result.blocks
            if b.block_type in (BlockType.HEADING, BlockType.NOTE)
        ]
        ambient_context = " ".join(context_snippets)

        # 1. Analyze Identified Question Groups
        if structure_result.questions:
            for q in structure_result.questions:
                item_analysis = self._analyze_question_entity(q, ambient_context)
                items.append(item_analysis)

        # 2. Analyze Non-Question Blocks (e.g. Paragraphs or Headings)
        for blk in structure_result.blocks:
            if blk.block_type in (BlockType.PARAGRAPH, BlockType.HEADING, BlockType.NOTE):
                item_analysis = self._analyze_general_block(blk, ambient_context)
                items.append(item_analysis)

        # Determine aggregate document domains
        all_domain_names: List[str] = []
        for it in items:
            if it.primary_domain and it.primary_domain not in all_domain_names:
                all_domain_names.append(it.primary_domain)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        metadata = {
            "document_id": document_id,
            "total_items_analyzed": len(items),
            "document_primary_domains": all_domain_names,
            "embedding_dimension": self._embedding_engine.dimension,
        }

        return SemanticAnalysisResult(
            items=items,
            document_domains=all_domain_names,
            processing_time_ms=round(elapsed_ms, 2),
            embedding_engine=self._embedding_engine.engine_name,
            status="SUCCESS",
            warnings=doc_warnings,
            metadata=metadata,
        )

    def analyze_text(
        self,
        text: str,
        context_text: str = "",
        source_id: str = "custom-query",
    ) -> SemanticItemAnalysis:
        """Analyze a standalone text string or question query."""
        return self._process_text(
            text=text,
            context_text=context_text,
            source_id=source_id,
            has_options=False,
            upstream_warnings=(),
        )

    def _analyze_question_entity(
        self,
        question: QuestionGroup,
        ambient_context: str,
    ) -> SemanticItemAnalysis:
        """Analyze a structured QuestionGroup."""
        # Include answer options in text representation for multi-choice context
        opt_text = " ".join(f"[{opt.option_label}] {opt.option_text}" for opt in question.options)
        combined_text = f"{question.question_text} {opt_text}".strip()

        return self._process_text(
            text=question.question_text,
            context_text=f"{ambient_context} {opt_text}",
            source_id=f"question-{question.question_block_id}",
            has_options=bool(question.options),
            upstream_warnings=question.warnings,
        )

    def _analyze_general_block(
        self,
        block: DocumentBlock,
        ambient_context: str,
    ) -> SemanticItemAnalysis:
        """Analyze a non-question document block."""
        return self._process_text(
            text=block.text,
            context_text=ambient_context,
            source_id=f"block-{block.block_id}",
            has_options=False,
            upstream_warnings=block.warnings,
        )

    def _process_text(
        self,
        text: str,
        context_text: str,
        source_id: str,
        has_options: bool,
        upstream_warnings: Sequence[str],
    ) -> SemanticItemAnalysis:
        """Core analysis pipeline for an individual text unit."""
        item_warnings: List[str] = list(upstream_warnings)

        # 1. Polysemous Term Disambiguation
        disambiguations = disambiguate_terms(text, context_text)
        for d in disambiguations:
            if "AMBIGUOUS" in d.resolved_sense:
                item_warnings.append(
                    f"Ambiguous term '{d.term}': context does not resolve between candidate senses {d.candidate_senses}."
                )

        # 2. Concept, Entity, and Relationship Extraction
        concepts, entities, relationships = extract_concepts_and_entities(text)

        # 3. Question Intent Classification
        intents = classify_question_intents(text, has_options=has_options)

        # 4. Technical Level Assessment
        tech_level = estimate_technical_level(text)

        # 5. Open-Vocabulary Domain Classification
        domains, dom_status, dom_warnings = self._domain_classifier.classify(
            text=text,
            context_text=context_text,
            disambiguations=disambiguations,
        )
        item_warnings.extend(dom_warnings)

        primary_domain = domains[0].domain_name if domains else None
        primary_topic = concepts[0].normalized_form if concepts else (primary_domain or "General")
        secondary_topics = tuple(c.normalized_form for c in concepts[1:4])

        # 6. Optional Local Knowledge Retrieval
        retrieved_knowledge = ()
        if self._retriever is not None and primary_domain:
            retrieved_knowledge = tuple(self._retriever.retrieve(text, threshold=0.30, top_k=1))

        # 7. Final Status Determination
        if dom_status in ("INSUFFICIENT_EVIDENCE", "UNKNOWN_DOMAIN"):
            status = dom_status
        elif any("AMBIGUOUS" in d.resolved_sense for d in disambiguations):
            status = "AMBIGUOUS"
        else:
            status = "ANALYZED"

        return SemanticItemAnalysis(
            source_id=source_id,
            original_text=text,
            normalized_text=concepts[0].normalized_form if concepts else None,
            primary_domain=primary_domain,
            domains=tuple(domains),
            primary_topic=primary_topic,
            secondary_topics=secondary_topics,
            concepts=tuple(concepts),
            entities=tuple(entities),
            relationships=tuple(relationships),
            question_intents=tuple(intents),
            technical_level=tech_level,
            ambiguities=tuple(disambiguations),
            warnings=tuple(item_warnings),
            retrieved_knowledge=retrieved_knowledge,
            classification_method=self._embedding_engine.engine_name,
            status=status,
        )
