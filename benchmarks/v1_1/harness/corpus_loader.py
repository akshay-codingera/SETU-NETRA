"""
corpus_loader.py: Ingestion and indexing coordinator for SETU-NETRA V1.1 benchmark corpus.
Loads fixed technical documents into an isolated test SQLite store.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple
from setu_netra.pipeline.document_pipeline import DocumentIntelligencePipeline
from setu_netra.store.sqlite_store import SQLiteDocumentStore

logger = logging.getLogger(__name__)


def setup_benchmark_corpus(
    db_path: str = "output/v1_1_benchmark_store.db",
    corpus_dir: str = "benchmarks/v1_1/corpus",
    force_reindex: bool = False,
) -> Tuple[DocumentIntelligencePipeline, Dict[str, str]]:
    """Ingests the fixed benchmark corpus files into an isolated database.

    Returns:
        (pipeline, doc_name_to_id_mapping)
    """
    db_file = Path(db_path)
    if force_reindex and db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass

    doc_pipeline = DocumentIntelligencePipeline(db_path=str(db_file))
    corpus_path = Path(corpus_dir)
    doc_mapping: Dict[str, str] = {}

    target_files = [
        "doc_operating_systems.txt",
        "doc_raft_consensus.txt",
        "doc_database_concurrency.txt",
    ]

    for fname in target_files:
        fpath = corpus_path / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Corpus file not found: {fpath}")

        # Ingest document
        stored = doc_pipeline.ingest_document(fpath)
        doc_mapping[fname] = stored.doc_id
        logger.info("Ingested %s -> doc_id=%s, pages=%d", fname, stored.doc_id, stored.page_count)

    return doc_pipeline, doc_mapping
