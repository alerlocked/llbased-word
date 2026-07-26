"""
Profile API - Domain-based profile management with condition-grouped knowledge, principles, and preferences.

Each domain (assembly, welding, coating, general) has its own profile file.
Endpoints use domain as the key instead of user_id.

Endpoints:
- GET    /api/profile/{domain}                    — Get profile for domain
- PUT    /api/profile/{domain}                    — Update writing/review config
- DELETE /api/profile/{domain}                    — Reset to default
- POST   /api/profile/{domain}/learn              — Learn from document content
- POST   /api/profile/{domain}/learn-file         — Learn from file

Knowledge CRUD:
- POST   /api/profile/{domain}/knowledge          — Add condition-grouped entry
- DELETE /api/profile/{domain}/knowledge/{id}     — Remove entry
- POST   /api/profile/{domain}/knowledge/merge    — Batch merge entries
- POST   /api/profile/{domain}/knowledge/search   — Search by entity/conditions

Principle CRUD:
- POST   /api/profile/{domain}/principles         — Add principle
- DELETE /api/profile/{domain}/principles/{id}    — Remove principle

Preference CRUD:
- POST   /api/profile/{domain}/preferences        — Add preference
- DELETE /api/profile/{domain}/preferences/{id}   — Remove preference
"""
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body, Query, Depends
from pydantic import BaseModel, Field

from app.shared.logging import get_logger
from app.models.profile import (
    Profile, ConditionGroup, Principle, Preference,
    WritingConfig, ReviewConfig,
    get_default_assembly_profile, get_default_welding_profile,
)
from app.services.document_profile_learner import DocumentProfileLearner
from app.services.knowledge_graph import craft_kg, save_craft_kg, KnowledgeGraph

import json
import re
from fastapi.responses import StreamingResponse
from app.models.database import Material
from app.database import Session, get_db
from app.services.feedback_learner import FeedbackLearner
from app.config import settings

logger = get_logger(__name__)

router = APIRouter()

PROFILES_DIR = Path(settings.DATA_DIR) / "profiles"

VALID_DOMAINS = {"assembly", "welding", "coating", "general"}


def _get_default_profile(domain: str) -> Profile:
    """Get the default profile for a given domain."""
    defaults = {
        "assembly": get_default_assembly_profile,
        "welding": get_default_welding_profile,
    }
    factory = defaults.get(domain)
    if factory:
        return factory()
    # Generic default for unknown domains
    return Profile(
        id=f"default_{domain}",
        user_id="default",
        domain=domain,
        writing=WritingConfig(),
        review=ReviewConfig(),
    )


# ========================================
# Request Models
# ========================================

class LearnRequest(BaseModel):
    content: str = Field(..., min_length=10)
    domain: str = Field(default="assembly")
    document_id: Optional[str] = None


class LearnFileRequest(BaseModel):
    file_path: str
    domain: str = Field(default="assembly")
    document_id: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    writing: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None


class KnowledgeEntryRequest(BaseModel):
    entity: str = Field(..., min_length=1)
    conditions: Dict[str, str] = Field(default_factory=dict)
    attributes: Dict[str, str] = Field(default_factory=dict)
    source: str = ""


class KnowledgeSearchRequest(BaseModel):
    entity: str
    conditions: Optional[Dict[str, str]] = None


class KnowledgeMergeRequest(BaseModel):
    entries: List[KnowledgeEntryRequest]


class PrincipleRequest(BaseModel):
    dimension: str = Field(..., pattern=r"^(text_compliance|data_validity|terminology)$")
    name: str = Field(..., min_length=1)
    description: str = ""
    check_expression: str = ""
    source: str = ""


class PrinciplePatchRequest(BaseModel):
    """Partial update for a principle (review UI enables/edits rules)."""
    enabled: Optional[bool] = None
    name: Optional[str] = None
    description: Optional[str] = None
    check_expression: Optional[str] = None


class CellEditItem(BaseModel):
    """One cell-level change the user made to generated content."""
    section_id: str = ""
    section_title: str = ""
    row_key: str = ""
    col_key: str = ""
    col_label: str = ""
    old_value: str = ""
    new_value: str = ""


class RowChangeItem(BaseModel):
    """A row added/removed by the user (fed to the inducer for completeness rules)."""
    section_id: str = ""
    section_title: str = ""
    change: str = ""  # "added" | "removed"
    row_data: Dict[str, Any] = Field(default_factory=dict)


class LearnFeedbackRequest(BaseModel):
    """User edits to generated content, to be induced into principles."""
    domain: str = Field(default="assembly")
    project_id: str = ""  # str — front-end treats IDs as strings (int64 precision)
    edits: List[CellEditItem] = Field(default_factory=list)
    row_changes: List[RowChangeItem] = Field(default_factory=list)
    skip_llm: bool = False


class PreferenceRequest(BaseModel):
    dimension: str = Field(..., pattern=r"^(readability|executability|style)$")
    category: str = Field(..., min_length=1)
    description: str = ""
    positive_examples: List[str] = Field(default_factory=list)
    negative_examples: List[str] = Field(default_factory=list)
    learned_from: str = "manual"
    source_ids: List[str] = Field(default_factory=list)


# ========================================
# Helpers
# ========================================

def _profile_path(domain: str) -> Path:
    return PROFILES_DIR / f"{domain}.json"


def _load_profile(domain: str) -> Profile:
    path = _profile_path(domain)
    if path.exists():
        return Profile.from_json(path)
    return _get_default_profile(domain)


def _save_profile(profile: Profile) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile.to_json(_profile_path(profile.domain))


# ========================================
# Core Profile Endpoints
# ========================================

@router.get("/{domain}")
def get_profile(domain: str) -> Dict[str, Any]:
    profile = _load_profile(domain)
    return {"status": "ok", "profile": profile.to_dict()}


@router.put("/{domain}")
def update_profile(domain: str, req: ProfileUpdateRequest) -> Dict[str, Any]:
    profile = _load_profile(domain)
    pd = profile.to_dict()

    if req.writing:
        pd["writing"].update(req.writing)
    if req.review:
        pd["review"].update(req.review)

    updated = Profile.from_dict(pd)
    _save_profile(updated)
    return {"status": "ok", "profile": updated.to_dict()}


@router.delete("/{domain}")
def reset_profile(domain: str) -> Dict[str, Any]:
    path = _profile_path(domain)
    if path.exists():
        path.unlink()
    default = _get_default_profile(domain)
    return {"status": "ok", "message": "Profile reset to default", "profile": default.to_dict()}


def _feed_craft_kg(triples: List[Dict[str, str]]) -> int:
    """Build a KG from learned triples, merge into the global craft_kg, persist.

    Returns the merged global craft_kg node count. Fail-soft: any error logs
    a warning and returns the current node_count — KG feed never blocks learning
    (craft-kg-from-learn: closes g25a-method-aux-bind N1 gap, N3 needs data).
    """
    if not triples:
        return craft_kg.node_count
    try:
        local = KnowledgeGraph.build_from_triples(triples)
        craft_kg.merge_from(local)
        save_craft_kg(craft_kg)
    except Exception as e:
        logger.warning(f"_feed_craft_kg failed: {e}")
    return craft_kg.node_count


@router.post("/{domain}/learn")
async def learn_from_content(domain: str, req: LearnRequest) -> Dict[str, Any]:
    """Learn profile features from document text content."""
    learner = DocumentProfileLearner()
    features = await learner.learn_from_content(
        content=req.content,
        domain=req.domain,
        document_id=req.document_id,
    )

    profile = _load_profile(domain)
    profile_dict = profile.to_dict()
    merged = learner.merge_features_to_profile(profile_dict, features)

    updated = Profile.from_dict(merged)
    _save_profile(updated)

    # Feed global craft KG (learn→triples→craft_kg, closes N3 empty-aux gap)
    kg_nodes = _feed_craft_kg(features.get("triples", []))

    return {
        "status": "ok",
        "message": f"Learned from document",
        "extracted_features": {
            "terms_count": len(features.get("frequent_terms", {})),
            "patterns_count": len(features.get("document_patterns", [])),
            "kg_nodes": kg_nodes,
        },
        "profile": updated.to_dict(),
    }


@router.post("/{domain}/learn-file")
async def learn_from_file(domain: str, req: LearnFileRequest) -> Dict[str, Any]:
    """Learn from a parsed document file."""
    file_path = Path(req.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {e}")

    content = raw
    if file_path.suffix == ".json":
        import json
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                if "pages" in data:
                    texts = []
                    for page in data.get("pages", []):
                        for block in page.get("blocks", []):
                            texts.append(block.get("text", ""))
                    content = "\n".join(texts)
                elif "content" in data:
                    c = data["content"]
                    content = "\n".join(str(item) for item in c) if isinstance(c, list) else str(c)
                elif "text" in data:
                    content = data["text"]
        except json.JSONDecodeError:
            pass

    doc_id = req.document_id or file_path.stem
    learner = DocumentProfileLearner()
    # G25a 装配文档：接 extract，process 用 G19a skeleton 真工序名（N2'）
    learn_kwargs: Dict[str, Any] = {}
    try:
        _mid = int(doc_id)
        from app.services.hierarchical_context import hierarchical_context as hc
        asm = hc.extract_assembly_steps(str(_mid))
        skel = hc.extract_process_steps(str(_mid))
        if asm:
            learn_kwargs = {"assembly_steps": asm, "skeleton_steps": skel}
    except Exception:
        pass
    features = await learner.learn_from_content(
        content=content, domain=req.domain, document_id=doc_id, **learn_kwargs
    )

    profile = _load_profile(domain)
    profile_dict = profile.to_dict()
    merged = learner.merge_features_to_profile(profile_dict, features)
    updated = Profile.from_dict(merged)
    _save_profile(updated)

    # Feed global craft KG (same as learn endpoint)
    kg_nodes = _feed_craft_kg(features.get("triples", []))

    return {
        "status": "ok",
        "message": f"Learned from file: {file_path.name}",
        "kg_nodes": kg_nodes,
        "profile": updated.to_dict(),
    }


class LearnBatchRequest(BaseModel):
    file_ids: List[str] = Field(default_factory=list)


def _read_material_content(material_id: int) -> str:
    """Read material content text — content.json first, content.html fallback.

    Mirrors creation.get_material_detail so batch-learn sees the same content
    as the single-file learn button (which fetches /materials/{id}).
    """
    from app.config import settings
    doc_dir = Path(settings.DATA_DIR) / "documents" / str(material_id)
    content_json = doc_dir / settings.DOC_CONTENT_JSON_FILE
    if content_json.exists():
        try:
            data = json.loads(content_json.read_text(encoding="utf-8"))
            c = data.get("content", "") if isinstance(data, dict) else ""
            if c:
                return c
        except Exception:
            pass
    html_path = settings.resolve_doc_content_html(doc_dir)
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return ""


def _html_to_text(html: str) -> str:
    """Strip HTML tags + collapse whitespace (matches frontend replace(/<[^>]+>/g,''))."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def _sse(data: Dict[str, Any]) -> str:
    """Format a Server-Sent Event line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{domain}/learn-batch")
async def learn_from_batch(
    domain: str, req: LearnBatchRequest, db: Session = Depends(get_db),
) -> StreamingResponse:
    """Batch-learn a folder of materials + feed global craft KG (SSE progress).

    Content is preloaded (sync, fast) before streaming so the generator holds
    no DB session; the slow LLM learn runs inside the stream, one progress
    event per file. Fail-soft per file: one bad file doesn't abort the batch.
    """
    items: List[tuple] = []  # (fid, name, domain, text, learn_kwargs)
    from app.services.hierarchical_context import hierarchical_context as hc
    for fid in req.file_ids:
        try:
            mid = int(fid)
        except (TypeError, ValueError):
            continue
        m = db.query(Material).filter(Material.id == mid).first()
        if not m:
            continue
        text = _html_to_text(_read_material_content(mid))
        if len(text) < 10:
            continue
        # G25a 装配文档：接 extract，process 用 G19a skeleton 真工序名（N2'）
        learn_kwargs: Dict[str, Any] = {}
        try:
            asm = hc.extract_assembly_steps(str(mid))
            skel = hc.extract_process_steps(str(mid))
            if asm:
                learn_kwargs = {"assembly_steps": asm, "skeleton_steps": skel}
        except Exception:
            pass
        items.append((str(mid), m.name or fid, m.specialty or domain, text, learn_kwargs))

    total = len(items)

    async def generate():
        yield _sse({"type": "start", "total": total})
        ok = 0
        for idx, (fid, name, fdomain, text, learn_kwargs) in enumerate(items, 1):
            try:
                learner = DocumentProfileLearner()
                features = await learner.learn_from_content(
                    content=text, domain=fdomain, document_id=fid, **learn_kwargs,
                )
                profile = _load_profile(fdomain)
                merged = learner.merge_features_to_profile(profile.to_dict(), features)
                updated = Profile.from_dict(merged)
                _save_profile(updated)
                kg_nodes = _feed_craft_kg(features.get("triples", []))
                ok += 1
                yield _sse({
                    "type": "progress", "current": idx, "total": total,
                    "file": name, "triples": len(features.get("triples", [])),
                    "kg_nodes": kg_nodes,
                })
            except Exception as e:
                logger.warning(f"learn-batch file {fid} failed: {e}")
                yield _sse({"type": "item_error", "file": name, "message": str(e)})
        yield _sse({
            "type": "complete", "total": total, "ok": ok,
            "kg_nodes": craft_kg.node_count,
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{domain}/learn-feedback")
async def learn_from_feedback(domain: str, req: LearnFeedbackRequest) -> Dict[str, Any]:
    """Induce principles from user edits to generated content (feedback-rules 节点3).

    Fail-soft: any error returns ok with added=0, never blocks the save that
    triggered the call. Principles enter with enabled=False (pending review)."""
    if not req.edits and not req.row_changes:
        return {"status": "ok", "message": "no edits", "added": 0, "principles": []}
    try:
        learner = FeedbackLearner()
        principles = await learner.learn_from_edits(
            edits=[e.model_dump() for e in req.edits],
            row_changes=[r.model_dump() for r in req.row_changes],
            domain=domain,
            project_id=req.project_id,
            skip_llm=req.skip_llm,
        )
        profile = _load_profile(domain)
        added = []
        for p in principles:
            pid = profile.add_principle(p)  # name+dimension dedup → idempotent
            added.append({"id": pid, **p.to_dict()})
        _save_profile(profile)
        return {"status": "ok", "added": len(added), "principles": added}
    except Exception as e:
        logger.warning("learn_feedback_failed", error=str(e))
        return {"status": "ok", "message": "feedback_learn_failed_silently", "added": 0, "principles": []}


# ========================================
# Knowledge CRUD
# ========================================

@router.post("/{domain}/knowledge")
def add_knowledge(domain: str, req: KnowledgeEntryRequest) -> Dict[str, Any]:
    """Add a condition-grouped knowledge entry. Auto-deduplicates by entity+conditions."""
    profile = _load_profile(domain)
    entry = ConditionGroup(
        entity=req.entity,
        conditions=req.conditions,
        attributes=req.attributes,
        source=req.source,
    )
    entry_id = profile.add_knowledge(entry)
    _save_profile(profile)
    return {"status": "ok", "id": entry_id, "profile": profile.to_dict()}


@router.delete("/{domain}/knowledge/{entry_id}")
def remove_knowledge(domain: str, entry_id: str) -> Dict[str, Any]:
    """Remove a knowledge entry by ID."""
    profile = _load_profile(domain)
    if not profile.remove_knowledge(entry_id):
        raise HTTPException(status_code=404, detail=f"Knowledge entry {entry_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}


@router.post("/{domain}/knowledge/merge")
def merge_knowledge(domain: str, req: KnowledgeMergeRequest) -> Dict[str, Any]:
    """Batch merge multiple knowledge entries. Returns count of new entries added."""
    profile = _load_profile(domain)
    entries = [
        ConditionGroup(entity=e.entity, conditions=e.conditions, attributes=e.attributes, source=e.source)
        for e in req.entries
    ]
    added = profile.merge_knowledge(entries)
    _save_profile(profile)
    return {"status": "ok", "added": added, "total": len(profile.knowledge), "profile": profile.to_dict()}


@router.post("/{domain}/knowledge/search")
def search_knowledge(domain: str, req: KnowledgeSearchRequest) -> Dict[str, Any]:
    """Search knowledge entries by entity and optional conditions."""
    profile = _load_profile(domain)
    results = profile.find_knowledge(req.entity, req.conditions)
    return {"status": "ok", "results": results, "count": len(results)}


# ========================================
# Principle CRUD
# ========================================

@router.post("/{domain}/principles")
def add_principle(domain: str, req: PrincipleRequest) -> Dict[str, Any]:
    """Add a compliance principle. Auto-deduplicates by name+dimension."""
    profile = _load_profile(domain)
    principle = Principle(
        dimension=req.dimension,
        name=req.name,
        description=req.description,
        check_expression=req.check_expression,
        source=req.source,
    )
    pid = profile.add_principle(principle)
    _save_profile(profile)
    return {"status": "ok", "id": pid, "profile": profile.to_dict()}


@router.delete("/{domain}/principles/{principle_id}")
def remove_principle(domain: str, principle_id: str) -> Dict[str, Any]:
    """Remove a principle by ID."""
    profile = _load_profile(domain)
    if not profile.remove_principle(principle_id):
        raise HTTPException(status_code=404, detail=f"Principle {principle_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}


@router.patch("/{domain}/principles/{principle_id}")
def patch_principle(domain: str, principle_id: str, req: PrinciplePatchRequest) -> Dict[str, Any]:
    """Patch a principle (enabled/name/description/check_expression).

    Used by the review UI to enable feedback_learned rules or edit any rule."""
    profile = _load_profile(domain)
    found = False
    for p in profile.principles:
        if p.get("id") == principle_id:
            if req.enabled is not None:
                p["enabled"] = req.enabled
            if req.name is not None:
                p["name"] = req.name
            if req.description is not None:
                p["description"] = req.description
            if req.check_expression is not None:
                p["check_expression"] = req.check_expression
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Principle {principle_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}


# ========================================
# Preference CRUD
# ========================================

@router.post("/{domain}/preferences")
def add_preference(domain: str, req: PreferenceRequest) -> Dict[str, Any]:
    """Add a learned preference. Auto-deduplicates by category+dimension."""
    profile = _load_profile(domain)
    pref = Preference(
        dimension=req.dimension,
        category=req.category,
        description=req.description,
        positive_examples=req.positive_examples,
        negative_examples=req.negative_examples,
        learned_from=req.learned_from,
        source_ids=req.source_ids,
    )
    pid = profile.add_preference(pref)
    _save_profile(profile)
    return {"status": "ok", "id": pid, "profile": profile.to_dict()}


@router.delete("/{domain}/preferences/{pref_id}")
def remove_preference(domain: str, pref_id: str) -> Dict[str, Any]:
    """Remove a preference by ID."""
    profile = _load_profile(domain)
    if not profile.remove_preference(pref_id):
        raise HTTPException(status_code=404, detail=f"Preference {pref_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}
