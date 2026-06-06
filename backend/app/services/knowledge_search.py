"""
Knowledge Search — Query the material catalog, process steps, and standard clauses.

Provides search methods used by the Knowledge Catalog layer in the context system,
and by WritingAgent / ReviewAgent for injecting structured knowledge.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.shared.logging import get_logger

logger = get_logger(__name__)


class KnowledgeSearchService:
    """Search across the material catalog, process steps, and standard clauses."""

    def search_materials(
        self,
        db: Session,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search material catalog by name, model, or standard code.

        Args:
            db: Database session
            query: Search text
            category: Filter by category (standard_part/consumable/tool/auxiliary)
            top_k: Max results

        Returns:
            List of material dicts
        """
        from app.models.database import MaterialCatalog

        q = db.query(MaterialCatalog)
        if category:
            q = q.filter(MaterialCatalog.category == category)

        # Search across name, model, standard_code
        like = f"%{query}%"
        q = q.filter(
            (MaterialCatalog.name.like(like))
            | (MaterialCatalog.model.like(like))
            | (MaterialCatalog.standard_code.like(like))
            | (MaterialCatalog.spec.like(like))
        )
        rows = q.limit(top_k).all()

        return [
            {
                "id": r.id,
                "category": r.category,
                "name": r.name,
                "brand": r.brand,
                "model": r.model,
                "standard_code": r.standard_code,
                "spec": r.spec,
                "unit": r.unit,
            }
            for r in rows
        ]

    def search_tools_for_step(
        self,
        db: Session,
        step_name: str,
    ) -> List[Dict[str, Any]]:
        """Find tools associated with a process step by name.

        Args:
            db: Database session
            step_name: Process step name (fuzzy match)

        Returns:
            List of tool dicts
        """
        from app.models.database import MaterialCatalog, ProcessStep, StepTool

        # Find matching steps
        steps = db.query(ProcessStep).filter(
            ProcessStep.step_name.like(f"%{step_name}%")
        ).all()

        if not steps:
            return []

        step_ids = [s.id for s in steps]
        # Get tool associations
        tool_links = db.query(StepTool).filter(
            StepTool.step_id.in_(step_ids)
        ).all()

        if not tool_links:
            return []

        catalog_ids = [tl.catalog_id for tl in tool_links]
        tools = db.query(MaterialCatalog).filter(
            MaterialCatalog.id.in_(catalog_ids)
        ).all()

        return [
            {"id": t.id, "name": t.name, "model": t.model, "spec": t.spec}
            for t in tools
        ]

    def search_materials_for_step(
        self,
        db: Session,
        step_name: str,
    ) -> List[Dict[str, Any]]:
        """Find materials associated with a process step by name.

        Args:
            db: Database session
            step_name: Process step name (fuzzy match)

        Returns:
            List of material dicts with usage info
        """
        from app.models.database import MaterialCatalog, ProcessStep, StepMaterial

        steps = db.query(ProcessStep).filter(
            ProcessStep.step_name.like(f"%{step_name}%")
        ).all()

        if not steps:
            return []

        step_ids = [s.id for s in steps]
        mat_links = db.query(StepMaterial).filter(
            StepMaterial.step_id.in_(step_ids)
        ).all()

        if not mat_links:
            return []

        catalog_ids = [ml.catalog_id for ml in mat_links]
        materials = db.query(MaterialCatalog).filter(
            MaterialCatalog.id.in_(catalog_ids)
        ).all()

        # Build lookup for usage info
        link_map = {ml.catalog_id: ml for ml in mat_links}

        return [
            {
                "id": m.id,
                "name": m.name,
                "model": m.model,
                "unit": m.unit,
                "spec": m.spec,
                "usage_type": link_map.get(m.id, {}).usage_type if m.id in {ml.catalog_id for ml in mat_links} else None,
                "quantity": link_map.get(m.id, {}).quantity if m.id in {ml.catalog_id for ml in mat_links} else None,
            }
            for m in materials
        ]

    def search_standard_clauses(
        self,
        db: Session,
        query: str,
        clause_type: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search standard clauses by requirement text.

        Args:
            db: Database session
            query: Search text
            clause_type: Filter by type (format/process/quality/safety)
            top_k: Max results

        Returns:
            List of clause dicts with standard info
        """
        from app.models.database import Standard, StandardClause

        q = db.query(StandardClause).join(Standard)
        if clause_type:
            q = q.filter(StandardClause.clause_type == clause_type)

        like = f"%{query}%"
        q = q.filter(StandardClause.requirement.like(like))
        rows = q.limit(top_k).all()

        return [
            {
                "id": r.id,
                "standard_code": r.standard.code,
                "standard_title": r.standard.title,
                "clause_number": r.clause_number,
                "requirement": r.requirement,
                "clause_type": r.clause_type,
                "applies_to": r.applies_to,
            }
            for r in rows
        ]

    def get_full_step_context(
        self,
        db: Session,
        step_name: str,
    ) -> Dict[str, Any]:
        """Get complete context for a process step: tools + materials.

        Used by WritingAgent to inject relevant knowledge when writing
        about a specific process step.

        Returns:
            {"step": {...}, "tools": [...], "materials": [...]}
        """
        from app.models.database import ProcessStep

        steps = db.query(ProcessStep).filter(
            ProcessStep.step_name.like(f"%{step_name}%")
        ).all()

        if not steps:
            return {"step": None, "tools": [], "materials": []}

        # Use the first match
        step = steps[0]
        tools = self.search_tools_for_step(db, step.step_name)
        materials = self.search_materials_for_step(db, step.step_name)

        return {
            "step": {
                "id": step.id,
                "name": step.step_name,
                "description": step.description,
                "doc_id": step.doc_id,
            },
            "tools": tools,
            "materials": materials,
        }

    def build_knowledge_context_text(
        self,
        db: Session,
        query: str,
        max_items: int = 5,
    ) -> str:
        """Build a text block suitable for injection into an LLM prompt.

        Searches materials, tools, and standard clauses, and formats
        them into a concise reference text.

        Returns:
            Formatted text block (empty string if nothing found)
        """
        parts: List[str] = []

        # Search materials
        materials = self.search_materials(db, query, top_k=max_items)
        if materials:
            parts.append("## 物料参考")
            for m in materials:
                line = f"- {m['name']}"
                if m.get("model"):
                    line += f" ({m['model']})"
                if m.get("standard_code"):
                    line += f" [标准: {m['standard_code']}]"
                if m.get("unit"):
                    line += f" 单位: {m['unit']}"
                parts.append(line)

        # Search tools for step
        tools = self.search_tools_for_step(db, query)
        if tools:
            parts.append("\n## 相关工具")
            for t in tools:
                line = f"- {t['name']}"
                if t.get("model"):
                    line += f" ({t['model']})"
                parts.append(line)

        # Search standard clauses
        clauses = self.search_standard_clauses(db, query, top_k=3)
        if clauses:
            parts.append("\n## 相关标准条款")
            for c in clauses:
                line = f"- [{c['standard_code']}"
                if c.get("clause_number"):
                    line += f" {c['clause_number']}"
                line += f"] {c['requirement'][:100]}"
                parts.append(line)

        return "\n".join(parts) if parts else ""
