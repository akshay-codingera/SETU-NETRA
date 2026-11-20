"""
Semantic understanding and domain classification package for SETU-NETRA (Module 4).
"""

from setu_netra.semantic.engine import SemanticUnderstandingEngine
from setu_netra.semantic.embeddings.factory import get_embedding_engine
from setu_netra.semantic.domain.taxonomy import DomainTaxonomy, DomainDefinition
from setu_netra.semantic.domain.classifier import OpenVocabularyDomainClassifier
from setu_netra.semantic.domain.disambiguation import disambiguate_terms

__all__ = [
    "SemanticUnderstandingEngine",
    "get_embedding_engine",
    "DomainTaxonomy",
    "DomainDefinition",
    "OpenVocabularyDomainClassifier",
    "disambiguate_terms",
]
