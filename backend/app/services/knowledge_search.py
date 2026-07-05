"""
Knowledge Search — Query the material catalog, process steps, and standard clauses.

Provides search methods used by the Knowledge Catalog layer in the context system,
and by WritingAgent / ReviewAgent for injecting structured knowledge.

Restored in revive-extract-funnel (Step 2): ORM tables now defined in
app.models.database (MaterialCatalog/ProcessStep/Standard/StandardClause/
StepMaterial/StepTool), populated by KnowledgeExtractor/StandardExtractor.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.shared.logging import get_logger

logger = get_logger(__name__)


class KnowledgeSearchService:
    """Search across material catalog, process steps, and standard clauses.

    All methods hit the structured tables populated by KnowledgeExtractor
    (material_catalog / process_steps) and StandardExtractor (standards /
    standard_clauses). StepMaterial/StepTool associations are not yet populated
    by extract_and_save (TODO), so step-scoped tool/material queries return
    empty until that wiring lands.
    """

    def search_materials(
        self,
        db: Session,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        specialty: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search material catalog by name/model/standard_code (LIKE).

        specialty: optional 检索穿透 filter (cleanup-and-dimensions 维度).
        """
        from app.models.database import MaterialCatalog
        like = f"%{query}%"
        q = db.query(MaterialCatalog).filter(
            MaterialCatalog.name.like(like)
            | MaterialCatalog.model.like(like)
            | MaterialCatalog.standard_code.like(like)
        )
        if category:
            q = q.filter(MaterialCatalog.category == category)
        if specialty:
            q = q.filter(MaterialCatalog.specialty == specialty)
        return [self._material_to_dict(r) for r in q.limit(top_k).all()]

    def search_tools_for_step(
        self, db: Session, step_name: str,
    ) -> List[Dict[str, Any]]:
        """Find tools associated with a process step (ProcessStep → StepTool → MaterialCatalog)."""
        from app.models.database import ProcessStep, StepTool, MaterialCatalog
        step = db.query(ProcessStep).filter(ProcessStep.step_name == step_name).first()
        if not step:
            return []
        tools = (
            db.query(MaterialCatalog)
            .join(StepTool, StepTool.catalog_id == MaterialCatalog.id)
            .filter(StepTool.step_id == step.id)
            .all()
        )
        return [self._material_to_dict(t) for t in tools]

    def search_materials_for_step(
        self, db: Session, step_name: str,
    ) -> List[Dict[str, Any]]:
        """Find materials associated with a process step (ProcessStep → StepMaterial → MaterialCatalog)."""
        from app.models.database import ProcessStep, StepMaterial, MaterialCatalog
        step = db.query(ProcessStep).filter(ProcessStep.step_name == step_name).first()
        if not step:
            return []
        mats = (
            db.query(MaterialCatalog)
            .join(StepMaterial, StepMaterial.catalog_id == MaterialCatalog.id)
            .filter(StepMaterial.step_id == step.id)
            .all()
        )
        return [self._material_to_dict(m) for m in mats]

    def search_standard_clauses(
        self,
        db: Session,
        query: str,
        clause_type: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search standard clauses by requirement text (LIKE)."""
        from app.models.database import StandardClause
        q = db.query(StandardClause).filter(
            StandardClause.requirement.like(f"%{query}%")
        )
        if clause_type:
            q = q.filter(StandardClause.clause_type == clause_type)
        return [self._clause_to_dict(r) for r in q.limit(top_k).all()]

    def get_full_step_context(
        self, db: Session, step_name: str,
    ) -> Dict[str, Any]:
        """Get complete context for a process step: tools + materials."""
        from app.models.database import ProcessStep
        step = db.query(ProcessStep).filter(ProcessStep.step_name == step_name).first()
        if not step:
            return {"step": None, "tools": [], "materials": []}
        return {
            "step": {
                "step_name": step.step_name,
                "doc_id": step.doc_id,
                "specialty": step.specialty,
            },
            "tools": self.search_tools_for_step(db, step_name),
            "materials": self.search_materials_for_step(db, step_name),
        }

    def build_knowledge_context_text(
        self, db: Session, query: str, max_items: int = 5,
    ) -> str:
        """Build a text block suitable for injection into an LLM prompt."""
        materials = self.search_materials(db, query, top_k=max_items)
        clauses = self.search_standard_clauses(db, query, top_k=max_items)
        parts: List[str] = []
        if materials:
            parts.append("相关物料:")
            for m in materials:
                parts.append(f"  - {m['name']}（型号:{m.get('model') or ''} 规格:{m.get('spec') or ''}）")
        if clauses:
            parts.append("相关标准条款:")
            for c in clauses:
                req = (c.get("requirement") or "")[:80]
                parts.append(f"  - [{c.get('clause_number') or ''}] {req}")
        return "\n".join(parts)

    @staticmethod
    def _material_to_dict(m) -> Dict[str, Any]:
        return {
            "id": m.id, "name": m.name, "category": m.category,
            "model": m.model, "standard_code": m.standard_code,
            "spec": m.spec, "unit": m.unit, "source_doc": m.source_doc,
            "specialty": m.specialty,
        }

    @staticmethod
    def _clause_to_dict(c) -> Dict[str, Any]:
        return {
            "id": c.id, "standard_id": c.standard_id,
            "clause_number": c.clause_number, "requirement": c.requirement,
            "clause_type": c.clause_type, "applies_to": c.applies_to,
        }
