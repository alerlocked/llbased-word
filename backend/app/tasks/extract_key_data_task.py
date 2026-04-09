"""
Key-data extraction task (Celery-compatible shim).

Background:
- `NodeDocumentWriter.write_node_document()` publishes an async task via
  `extract_key_data_task.delay(doc_id)`.
- The repository currently does not define a Celery app (and may run without a
  worker). Missing this module breaks the import path and makes the codebase
  feel "route-messy".

Design:
- Provide a minimal `.delay()` interface so existing call sites keep working.
- Execute extraction inline (best-effort) to keep the workflow running.
- If you later introduce a real Celery app, you can replace this shim with a
  real `@celery_app.task` without changing call sites.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.database import NodeDocument
from app.shared.logging import get_logger
logger = get_logger(__name__)


def _safe_extract_key_data(doc: NodeDocument) -> Dict[str, Any]:
    """
    Best-effort key_data extraction.

    Notes:
    - Today we keep this intentionally conservative: do NOT call LLM here.
      The goal is stability and deterministic behavior.
    - We extract only a few universally useful fields for routing / UI.
    - If you later want richer extraction (facts/issues/events), implement it
      in a separate service and call it from here.
    """
    data = doc.document_data or {}
    output = (data.get("output") or {}) if isinstance(data, dict) else {}

    # Minimal "selections" surface: used by deterministic routers / UI.
    selections: Dict[str, Any] = {}
    if doc.node_type == "analysis":
        # improvement solutions -> option ids
        sols = output.get("solutions") or []
        if isinstance(sols, list):
            selections["solution_option_ids"] = [
                (s.get("id") if isinstance(s, dict) else None) for s in sols
            ]
            selections["solution_option_ids"] = [x for x in selections["solution_option_ids"] if x]

    if doc.node_type == "planning":
        opts = output.get("plan_options") or []
        if isinstance(opts, list):
            selections["plan_option_ids"] = [
                (p.get("id") if isinstance(p, dict) else None) for p in opts
            ]
            selections["plan_option_ids"] = [x for x in selections["plan_option_ids"] if x]

    # Minimal "content" surface: useful for review/timeline preview.
    content_preview: Optional[str] = None
    if doc.node_type == "writing":
        content = output.get("content")
        if isinstance(content, str) and content:
            content_preview = content[:400]

    return {
        "node": {
            "id": doc.id,
            "name": doc.node_name,
            "type": doc.node_type,
            "state": doc.state,
        },
        "selections": selections,
        "content_preview": content_preview,
    }


def extract_key_data(doc_id: int) -> bool:
    """
    Extract and persist key_data for a NodeDocument.

    Returns:
        True if updated; False if doc not found or failed.
    """
    db: Session = SessionLocal()
    try:
        doc = db.query(NodeDocument).filter(NodeDocument.id == doc_id).first()
        if not doc:
            logger.warning(f"⚠️ [extract_key_data] NodeDocument not found: id={doc_id}")
            return False

        doc.key_data = _safe_extract_key_data(doc)
        db.commit()
        logger.info(f"✅ [extract_key_data] key_data updated: id={doc_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"❌ [extract_key_data] failed: id={doc_id}, err={e}")
        return False
    finally:
        db.close()


class _TaskShim:
    """
    Celery-like shim object.

    We only implement `.delay()` because call sites use it.
    """

    def delay(self, doc_id: int) -> bool:  # noqa: D401
        # Run inline to keep the system stable without a worker.
        return extract_key_data(doc_id)


# Public symbol expected by `NodeDocumentWriter`
extract_key_data_task = _TaskShim()

