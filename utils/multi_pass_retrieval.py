"""
utils/multi_pass_retrieval.py — Multi-Pass Knowledge Base Retrieval Helper

Implements the multi-pass retrieval pattern from the OpenAI data agent architecture:
  Pass 1 — execute the query with existing context
  Pass 2 — if answer is wrong/empty, identify the missing knowledge type and
            retrieve a targeted KB document
  Pass 3 — re-inject the retrieved document and retry

This module wraps the InjectionTester and is used by the agent to dynamically
augment its context when a query fails rather than retrying with the same context.

Usage:
    from utils.multi_pass_retrieval import MultiPassRetriever

    retriever = MultiPassRetriever(kb_root="kb/")

    # Check if a failed answer suggests a missing KB document
    doc_path = retriever.suggest_document(question, failed_answer, failure_mode)

    # Retrieve document text for context injection
    context_text = retriever.retrieve(doc_path)

    # Full retry loop: attempt query, diagnose failure, inject KB doc, retry
    result = retriever.retrieve_and_retry(
        question=question,
        attempt_fn=lambda ctx: agent_call(question, extra_context=ctx),
        validate_fn=lambda ans: ans.strip() != "" and "error" not in ans.lower(),
        max_passes=3,
    )
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Mapping from failure signal keywords to KB document paths
_FAILURE_SIGNAL_MAP: dict[str, str] = {
    # Join key failures → join_keys.md
    "businessid": "domain/join_keys.md",
    "businessref": "domain/join_keys.md",
    "join": "domain/join_keys.md",
    "0 rows": "domain/join_keys.md",
    "zero rows": "domain/join_keys.md",
    "prefix": "domain/join_keys.md",
    # Unstructured text failures → unstructured_fields.md
    "description": "domain/unstructured_fields.md",
    "extract": "domain/unstructured_fields.md",
    "regex": "domain/unstructured_fields.md",
    "text field": "domain/unstructured_fields.md",
    # Domain term failures → domain_terms.md
    "active customer": "domain/domain_terms.md",
    "churn": "domain/domain_terms.md",
    "up day": "domain/domain_terms.md",
    "fiscal": "domain/domain_terms.md",
    # Date format failures → query_patterns.md
    "strptime": "domain/query_patterns.md",
    "date format": "domain/query_patterns.md",
    "TRY_STRPTIME": "domain/query_patterns.md",
    # Schema / routing failures → dab_schemas.md
    "unknown db_name": "domain/dab_schemas.md",
    "table not found": "domain/dab_schemas.md",
    "no such table": "domain/dab_schemas.md",
    # MCP issues → architecture/mcp-toolbox-patterns.md
    "connection refused": "architecture/mcp-toolbox-patterns.md",
    "mcp": "architecture/mcp-toolbox-patterns.md",
}


class MultiPassRetriever:
    """
    Retrieves KB documents targeted at specific failure modes and optionally
    re-runs a query with the retrieved context injected.
    """

    def __init__(self, kb_root: str = "kb/") -> None:
        self.kb_root = Path(kb_root)

    def suggest_document(
        self,
        question: str,
        failed_answer: str,
        failure_mode: Optional[str] = None,
    ) -> Optional[str]:
        """
        Given a question and the agent's failed answer, suggest the most relevant
        KB document to retrieve for context injection.

        Args:
            question: The original natural language question.
            failed_answer: The agent's incorrect or empty answer.
            failure_mode: Optional explicit failure category (join_key, unstructured,
                          domain_gap, multi_db_routing).

        Returns:
            Relative path from kb_root to the suggested document, or None if
            no targeted document is identified.
        """
        combined = f"{question} {failed_answer} {failure_mode or ''}".lower()

        for signal, doc_path in _FAILURE_SIGNAL_MAP.items():
            if signal.lower() in combined:
                full_path = self.kb_root / doc_path
                if full_path.exists():
                    logger.info(
                        "MultiPassRetriever: signal '%s' → suggesting %s", signal, doc_path
                    )
                    return doc_path
                logger.warning(
                    "MultiPassRetriever: suggested %s but file not found", full_path
                )

        return None

    def retrieve(self, doc_path: str) -> str:
        """
        Return the text content of a KB document.

        Args:
            doc_path: Relative path from kb_root (e.g. 'domain/join_keys.md').

        Returns:
            Document text, or empty string if the file does not exist.
        """
        full_path = self.kb_root / doc_path
        if not full_path.exists():
            logger.warning("MultiPassRetriever.retrieve: file not found: %s", full_path)
            return ""
        return full_path.read_text(encoding="utf-8")

    def retrieve_and_retry(
        self,
        question: str,
        attempt_fn: Callable[[str], Any],
        validate_fn: Callable[[Any], bool],
        failure_mode: Optional[str] = None,
        max_passes: int = 3,
    ) -> dict[str, Any]:
        """
        Execute a multi-pass retrieval loop:
          1. Call attempt_fn with empty extra context.
          2. If validate_fn(result) is False, suggest a KB document.
          3. Retrieve it and call attempt_fn again with the document as extra context.
          4. Repeat up to max_passes times.

        Args:
            question: The NL question being answered.
            attempt_fn: Callable(extra_context: str) → answer. The agent call.
            validate_fn: Callable(answer) → bool. Returns True if answer is acceptable.
            failure_mode: Optional explicit failure category hint.
            max_passes: Maximum number of retrieval passes (default 3).

        Returns:
            dict with keys:
              - "answer": the final answer (best attempt)
              - "passes": number of passes used
              - "retrieved_docs": list of doc paths retrieved
              - "succeeded": bool — whether validate_fn passed
        """
        retrieved_docs: list[str] = []
        extra_context = ""
        answer: Any = None

        for pass_num in range(1, max_passes + 1):
            logger.info("MultiPassRetriever: pass %d/%d", pass_num, max_passes)
            answer = attempt_fn(extra_context)

            if validate_fn(answer):
                logger.info("MultiPassRetriever: validated on pass %d", pass_num)
                return {
                    "answer": answer,
                    "passes": pass_num,
                    "retrieved_docs": retrieved_docs,
                    "succeeded": True,
                }

            if pass_num == max_passes:
                break

            # Diagnose and retrieve
            answer_str = str(answer)
            doc_path = self.suggest_document(question, answer_str, failure_mode)
            if doc_path is None or doc_path in retrieved_docs:
                logger.info(
                    "MultiPassRetriever: no new document to retrieve — stopping at pass %d",
                    pass_num,
                )
                break

            doc_text = self.retrieve(doc_path)
            if not doc_text:
                break

            retrieved_docs.append(doc_path)
            extra_context = (
                f"\n\n---\n\n## RETRIEVED CONTEXT (pass {pass_num})\n\n{doc_text}"
            )
            logger.info(
                "MultiPassRetriever: retrieved %s (%d chars)", doc_path, len(doc_text)
            )

        return {
            "answer": answer,
            "passes": max_passes,
            "retrieved_docs": retrieved_docs,
            "succeeded": False,
        }
