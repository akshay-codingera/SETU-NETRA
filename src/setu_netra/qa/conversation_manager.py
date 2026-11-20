"""
conversation_manager.py: Persistent multi-turn conversation session coordinator.

Why this file exists:
In enterprise document intelligence, questions are rarely asked in isolation. Users ask
follow-up questions, request elaborations ("What does this mean?"), or compare sections.
This module maintains persistent conversation sessions in SQLite, applies bounded context
pruning, resolves coreference in follow-up queries, and preserves end-to-end citation provenance.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from setu_netra.qa.engine import EvidenceGroundedQAEngine, VerifiedAnswer
from setu_netra.store.sqlite_store import SQLiteDocumentStore

logger = logging.getLogger(__name__)

# Pronouns and deictic markers indicating a follow-up reference
REFERENCE_TRIGGERS = {
    "this", "that", "these", "those", "it", "its", "they", "them",
    "the second point", "the first point", "the third point",
    "previous section", "above", "earlier", "why", "how so",
    "elaborate", "explain further", "what do you mean",
}


class ConversationManager:
    """Coordinates persistent multi-turn conversations, follow-up query rewriting, and evidence grounding."""

    def __init__(self, store: SQLiteDocumentStore, qa_engine: EvidenceGroundedQAEngine):
        self._store = store
        self._qa_engine = qa_engine

    @property
    def store(self) -> SQLiteDocumentStore:
        return self._store

    @property
    def qa_engine(self) -> EvidenceGroundedQAEngine:
        return self._qa_engine

    def create_conversation(
        self,
        title: str = "New Conversation",
        user_id: str = "default_user",
        doc_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new conversation session associated with one or more documents."""
        metadata = {"doc_ids": doc_ids or []}
        conv_id = self._store.create_conversation(title=title, user_id=user_id, metadata=metadata)
        return {
            "conversation_id": conv_id,
            "title": title,
            "user_id": user_id,
            "doc_ids": doc_ids or [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    def list_conversations(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """List all conversation sessions for a user."""
        return self._store.list_conversations(user_id=user_id)

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation metadata and message history."""
        conv = self._store.get_conversation(conversation_id)
        if not conv:
            return None
        messages = self._store.get_messages(conversation_id, limit=100)
        conv["messages"] = messages
        return conv

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation session and all its messages."""
        return self._store.delete_conversation(conversation_id)

    def resolve_followup_query(self, query: str, recent_messages: List[Dict[str, Any]]) -> str:
        """Resolve pronouns and conversational references against recent conversation history.

        Uses a bounded heuristic to combine follow-up intent with focal concepts from the
        immediately preceding exchange without bloating prompt context.
        """
        cleaned = query.strip()
        lower_q = cleaned.lower()

        # Check if query contains deictic references or is a short follow-up
        words = set(re.findall(r"\b[a-zA-Z]+\b", lower_q))
        has_reference = bool(words & REFERENCE_TRIGGERS) or len(words) <= 4 or lower_q.startswith(("why", "how", "what about"))

        if not has_reference or not recent_messages:
            return cleaned

        # Find the most recent assistant message with content
        last_assistant_content = ""
        last_user_query = ""
        for msg in reversed(recent_messages):
            if msg["role"] == "assistant" and not last_assistant_content:
                last_assistant_content = msg["content"]
            elif msg["role"] == "user" and not last_user_query:
                last_user_query = msg["content"]
            if last_assistant_content and last_user_query:
                break

        if not last_assistant_content and not last_user_query:
            return cleaned

        # Extract primary focal subject (first sentence or key phrases up to 120 chars)
        focal_context = ""
        if last_assistant_content:
            first_sentence = re.split(r"[.\n]", last_assistant_content)[0].strip()
            # Strip citation brackets like [Doc: ...]
            first_sentence = re.sub(r"\[Doc:[^\]]+\]", "", first_sentence).strip()
            if len(first_sentence) > 15:
                focal_context = first_sentence[:150]

        if not focal_context and last_user_query:
            focal_context = last_user_query[:100]

        if focal_context:
            resolved = f"{cleaned} (Referring to: {focal_context})"
            logger.info("Resolved follow-up query '%s' -> '%s'", cleaned, resolved)
            return resolved

        return cleaned

    def ask(
        self,
        conversation_id: str,
        query: str,
        doc_id: Optional[str] = None,
        top_k: int = 3,
        model_id: Optional[str] = None,
        think: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Execute a conversational question answering turn and persist the exchange."""
        conv = self._store.get_conversation(conversation_id)
        if not conv:
            raise KeyError(f"Conversation '{conversation_id}' does not exist.")

        # Determine effective document filter
        effective_doc_id = doc_id
        if not effective_doc_id:
            conv_docs = conv.get("metadata", {}).get("doc_ids", [])
            if conv_docs:
                effective_doc_id = conv_docs[0]

        # 1. Retrieve recent history for bounded context resolution (last 4 messages)
        recent_history = self._store.get_messages(conversation_id, limit=4)

        # 2. Resolve follow-up query
        resolved_query = self.resolve_followup_query(query, recent_history)

        # 3. Record User Message
        user_msg_id = self._store.add_message(
            conversation_id=conversation_id,
            role="user",
            content=query,
            metadata={"resolved_query": resolved_query, "doc_id": effective_doc_id},
        )

        # 4. Execute Answer via Grounded QA Engine (which routes through InferencePipeline)
        verified_answer: VerifiedAnswer = self._qa_engine.answer_question(
            query=resolved_query,
            doc_id=effective_doc_id,
            top_k=top_k,
            model_id=model_id,
            think=think,
        )

        # 5. Record Assistant Message
        pipeline_meta = verified_answer.metadata or {}
        req_id = pipeline_meta.get("request_id") or f"req_{int(time.time()*1000)}"
        worker_id = pipeline_meta.get("worker_id") or "worker_default"
        thinking_trace = pipeline_meta.get("thinking") or pipeline_meta.get("pipeline_telemetry", {}).get("thinking")

        assistant_msg_id = self._store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=verified_answer.answer_text,
            model_id=verified_answer.executing_model_id,
            worker_id=worker_id,
            epistemic_status=verified_answer.epistemic_status,
            citations=verified_answer.citations,
            request_id=req_id,
            metadata={
                "grounding_score": verified_answer.grounding_score,
                "execution_time_ms": verified_answer.execution_time_ms,
                "explanation": verified_answer.explanation,
                "thinking": thinking_trace,
                "pipeline_telemetry": pipeline_meta.get("pipeline_telemetry", {}),
            },
        )

        # 6. Auto-title the conversation if on first turn or default title
        if conv["title"] in ("New Conversation", "Untitled") or len(recent_history) <= 1:
            title_words = query.strip().split()[:5]
            new_title = " ".join(title_words)
            if len(new_title) > 35:
                new_title = new_title[:32] + "..."
            with self._store._conn:
                self._store._conn.execute(
                    "UPDATE conversations SET title = ? WHERE conversation_id = ?;",
                    (new_title, conversation_id),
                )

        return {
            "conversation_id": conversation_id,
            "user_message_id": user_msg_id,
            "assistant_message_id": assistant_msg_id,
            "query": query,
            "resolved_query": resolved_query,
            "answer_text": verified_answer.answer_text,
            "epistemic_status": verified_answer.epistemic_status,
            "citations": verified_answer.citations,
            "grounding_score": verified_answer.grounding_score,
            "executing_model_id": verified_answer.executing_model_id,
            "executing_worker_id": worker_id,
            "execution_time_ms": verified_answer.execution_time_ms,
            "explanation": verified_answer.explanation,
            "thinking": thinking_trace,
            "pipeline_telemetry": pipeline_meta.get("pipeline_telemetry", {}),
            "answer": {
                "answer_text": verified_answer.answer_text,
                "epistemic_status": verified_answer.epistemic_status,
                "citations": verified_answer.citations,
                "grounding_score": verified_answer.grounding_score,
            },
        }
