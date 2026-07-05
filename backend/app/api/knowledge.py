"""
Knowledge API — Material catalog, standard library, and user event endpoints.

DEPRECATED: This router is NOT registered in main.py and the endpoints depend on
ORM tables (MaterialCatalog / ProcessStep / Standard / StandardClause) that are
not yet defined, plus KnowledgeExtractor / StandardExtractor services whose
backing models are also missing. Endpoints here will raise at call time.

Kept as a placeholder for Step F (cleanup-and-dimensions): once the catalog ORM
tables land and KnowledgeSearchService bodies are restored, re-register this
router in main.py. Do not call these endpoints in the meantime.

Provides REST endpoints for:
- Material catalog CRUD and search
- Standard clause search
- Knowledge extraction triggers
- User event recording and preference retrieval
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MaterialSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search text")
    category: Optional[str] = Field(None, description="Filter: standard_part/consumable/tool/auxiliary")
    top_k: int = Field(10, ge=1, le=50)


class MaterialResponse(BaseModel):
    id: int
    category: str
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    standard_code: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None


class StandardClauseResponse(BaseModel):
    id: int
    standard_code: str
    standard_title: str
    clause_number: Optional[str] = None
    requirement: str
    clause_type: Optional[str] = None
    applies_to: Optional[str] = None


class UserEventRequest(BaseModel):
    event_type: str = Field(..., description="edit/accept/reject/modify/create")
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    content_before: Optional[str] = None
    content_after: Optional[str] = None
    ai_suggestion: Optional[str] = None
    session_id: Optional[str] = None


class ExtractRequest(BaseModel):
    doc_id: str = Field(..., description="Document directory name, e.g. '1'")


class ExtractStandardRequest(BaseModel):
    dir_name: Optional[str] = Field(None, description="Specific standard dir; omit to extract all")


# ---------------------------------------------------------------------------
# Material catalog endpoints
# ---------------------------------------------------------------------------

@router.get("/materials/search", response_model=List[MaterialResponse])
async def search_materials(
    query: str = Query(..., min_length=1),
    category: Optional[str] = None,
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Search material catalog by name, model, or standard code."""
    from app.services.knowledge_search import KnowledgeSearchService
    svc = KnowledgeSearchService()
    return svc.search_materials(db, query, category=category, top_k=top_k)


@router.get("/materials/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: int, db: Session = Depends(get_db)):
    """Get a single material by ID."""
    from app.models.database import MaterialCatalog
    row = db.query(MaterialCatalog).filter_by(id=material_id).first()
    if not row:
        raise HTTPException(404, "Material not found")
    return MaterialResponse(
        id=row.id, category=row.category, name=row.name,
        brand=row.brand, model=row.model, standard_code=row.standard_code,
        spec=row.spec, unit=row.unit,
    )


# ---------------------------------------------------------------------------
# Standard clause endpoints
# ---------------------------------------------------------------------------

@router.get("/standards/search", response_model=List[StandardClauseResponse])
async def search_standard_clauses(
    query: str = Query(..., min_length=1),
    clause_type: Optional[str] = None,
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Search standard clauses by requirement text."""
    from app.services.knowledge_search import KnowledgeSearchService
    svc = KnowledgeSearchService()
    return svc.search_standard_clauses(db, query, clause_type=clause_type, top_k=top_k)


@router.get("/standards", response_model=List[Dict[str, Any]])
async def list_standards():
    """List all available QJ903 standard documents."""
    from app.services.standard_extractor import StandardExtractor
    ext = StandardExtractor()
    return ext.list_standards()


# ---------------------------------------------------------------------------
# Process step context endpoint
# ---------------------------------------------------------------------------

@router.get("/steps/context")
async def get_step_context(
    step_name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """Get full context for a process step: tools + materials."""
    from app.services.knowledge_search import KnowledgeSearchService
    svc = KnowledgeSearchService()
    return svc.get_full_step_context(db, step_name)


# ---------------------------------------------------------------------------
# Extraction endpoints
# ---------------------------------------------------------------------------

@router.post("/extract/document")
async def extract_from_document(
    req: ExtractRequest,
    db: Session = Depends(get_db),
):
    """Extract knowledge from a parsed document and save to DB."""
    from app.services.knowledge_extractor import KnowledgeExtractor
    ext = KnowledgeExtractor()
    try:
        counts = ext.extract_and_save(req.doc_id, db)
        return {"success": True, "counts": counts}
    except Exception as e:
        logger.error(f"[API] 知识提取失败: {e}")
        raise HTTPException(500, f"Extraction failed: {e}")


@router.post("/extract/standards")
async def extract_standards(
    req: ExtractStandardRequest = ExtractStandardRequest(),
    db: Session = Depends(get_db),
):
    """Extract standard clauses from QJ903 documents and save to DB."""
    from app.services.standard_extractor import StandardExtractor
    ext = StandardExtractor()
    try:
        if req.dir_name:
            counts = ext.extract_and_save(req.dir_name, db)
        else:
            counts = ext.extract_all_standards(db)
        return {"success": True, "counts": counts}
    except Exception as e:
        logger.error(f"[API] 标准提取失败: {e}")
        raise HTTPException(500, f"Standard extraction failed: {e}")


# ---------------------------------------------------------------------------
# User event endpoints
# ---------------------------------------------------------------------------

@router.post("/events")
async def record_event(
    req: UserEventRequest,
    db: Session = Depends(get_db),
):
    """Record a user action event (edit/accept/reject/modify/create)."""
    from app.services.preference_learner import PreferenceLearner
    try:
        event_id = PreferenceLearner.record_event(
            db=db,
            event_type=req.event_type,
            target_type=req.target_type,
            target_id=req.target_id,
            content_before=req.content_before,
            content_after=req.content_after,
            ai_suggestion=req.ai_suggestion,
            session_id=req.session_id,
        )
        return {"success": True, "event_id": event_id}
    except Exception as e:
        logger.error(f"[API] 事件记录失败: {e}")
        raise HTTPException(500, f"Event recording failed: {e}")


@router.get("/preferences")
async def get_preferences():
    """Get the current user preference profile."""
    from app.services.preference_learner import PreferenceLearner
    learner = PreferenceLearner()
    profile = learner.load_profile()
    return profile


@router.post("/preferences/analyze")
async def analyze_preferences(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Trigger LLM-based analysis of user events and update preferences."""
    from app.services.preference_learner import PreferenceLearner
    learner = PreferenceLearner()
    try:
        profile = await learner.analyze_and_update(db, days=days)
        return {"success": True, "profile": profile}
    except Exception as e:
        logger.error(f"[API] 偏好分析失败: {e}")
        raise HTTPException(500, f"Preference analysis failed: {e}")


# ---------------------------------------------------------------------------
# Knowledge context endpoint (for agent integration)
# ---------------------------------------------------------------------------

@router.get("/context")
async def get_knowledge_context(
    query: str = Query(..., min_length=1),
    max_items: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Get formatted knowledge context text for LLM injection."""
    from app.services.knowledge_search import KnowledgeSearchService
    svc = KnowledgeSearchService()
    text = svc.build_knowledge_context_text(db, query, max_items=max_items)
    return {"context": text, "has_content": bool(text)}
