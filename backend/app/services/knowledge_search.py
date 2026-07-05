"""
Knowledge Search — Query the material catalog, process steps, and standard clauses.

Provides search methods used by the Knowledge Catalog layer in the context system,
and by WritingAgent / ReviewAgent for injecting structured knowledge.

NOTE: The ORM models backing these queries (MaterialCatalog / ProcessStep /
Standard / StandardClause / StepTool / StepMaterial) are not yet defined in
app.models.database. All methods are stubbed to return empty results so the
service stays importable. Restore the ORM imports and bodies in Step F
(cleanup-and-dimensions node) when the catalog tables land.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.shared.logging import get_logger

logger = get_logger(__name__)


class KnowledgeSearchService:
    """Search across the material catalog, process steps, and standard clauses.

    All methods currently return empty results (see module docstring). The
    original SQL-backed bodies are intentionally suppressed until the catalog
    ORM tables are defined in Step F.
    """

    def search_materials(
        self,
        db: Session,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search material catalog by name, model, or standard code.

        Stub — restore ORM query in Step F (MaterialCatalog table).
        """
        return []

    def search_tools_for_step(
        self,
        db: Session,
        step_name: str,
    ) -> List[Dict[str, Any]]:
        """Find tools associated with a process step by name.

        Stub — restore ORM query in Step F (ProcessStep / StepTool tables).
        """
        return []

    def search_materials_for_step(
        self,
        db: Session,
        step_name: str,
    ) -> List[Dict[str, Any]]:
        """Find materials associated with a process step by name.

        Stub — restore ORM query in Step F (ProcessStep / StepMaterial tables).
        """
        return []

    def search_standard_clauses(
        self,
        db: Session,
        query: str,
        clause_type: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search standard clauses by requirement text.

        Stub — restore ORM query in Step F (Standard / StandardClause tables).
        """
        return []

    def get_full_step_context(
        self,
        db: Session,
        step_name: str,
    ) -> Dict[str, Any]:
        """Get complete context for a process step: tools + materials.

        Stub — restore ORM query in Step F (ProcessStep table).
        """
        return {"step": None, "tools": [], "materials": []}

    def build_knowledge_context_text(
        self,
        db: Session,
        query: str,
        max_items: int = 5,
    ) -> str:
        """Build a text block suitable for injection into an LLM prompt.

        Stub — returns empty string until catalog tables land in Step F.
        """
        return ""
