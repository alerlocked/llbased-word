"""
Profile API - User profile management with condition-grouped knowledge, principles, and preferences.

Endpoints:
- GET    /api/profile/{user_id}                    — Get current profile
- PUT    /api/profile/{user_id}                    — Update writing/review config
- DELETE /api/profile/{user_id}                    — Reset to default
- POST   /api/profile/{user_id}/learn              — Learn from document content
- POST   /api/profile/{user_id}/learn-file         — Learn from file

Knowledge CRUD:
- POST   /api/profile/{user_id}/knowledge          — Add condition-grouped entry
- DELETE /api/profile/{user_id}/knowledge/{id}     — Remove entry
- POST   /api/profile/{user_id}/knowledge/merge    — Batch merge entries
- GET    /api/profile/{user_id}/knowledge/search   — Search by entity/conditions

Principle CRUD:
- POST   /api/profile/{user_id}/principles         — Add principle
- DELETE /api/profile/{user_id}/principles/{id}    — Remove principle

Preference CRUD:
- POST   /api/profile/{user_id}/preferences        — Add preference
- DELETE /api/profile/{user_id}/preferences/{id}   — Remove preference
"""
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel, Field

from app.shared.logging import get_logger
from app.models.profile import (
    Profile, ConditionGroup, Principle, Preference,
    WritingConfig, ReviewConfig, get_default_assembly_profile,
)
from app.services.document_profile_learner import DocumentProfileLearner
from app.config import settings

logger = get_logger(__name__)

router = APIRouter()

PROFILES_DIR = Path(settings.DATA_DIR) / "profiles"


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
    severity: str = Field(default="error", pattern=r"^(error|warning)$")
    source: str = ""


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

def _profile_path(user_id: str) -> Path:
    return PROFILES_DIR / f"{user_id}.json"


def _load_profile(user_id: str) -> Profile:
    path = _profile_path(user_id)
    if path.exists():
        return Profile.from_json(path)
    return get_default_assembly_profile()


def _save_profile(profile: Profile) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile.to_json(_profile_path(profile.user_id))


# ========================================
# Core Profile Endpoints
# ========================================

@router.get("/{user_id}")
def get_profile(user_id: str) -> Dict[str, Any]:
    profile = _load_profile(user_id)
    return {"status": "ok", "profile": profile.to_dict()}


@router.put("/{user_id}")
def update_profile(user_id: str, req: ProfileUpdateRequest) -> Dict[str, Any]:
    profile = _load_profile(user_id)
    pd = profile.to_dict()

    if req.writing:
        pd["writing"].update(req.writing)
    if req.review:
        pd["review"].update(req.review)

    updated = Profile.from_dict(pd)
    _save_profile(updated)
    return {"status": "ok", "profile": updated.to_dict()}


@router.delete("/{user_id}")
def reset_profile(user_id: str) -> Dict[str, Any]:
    path = _profile_path(user_id)
    if path.exists():
        path.unlink()
    default = get_default_assembly_profile()
    return {"status": "ok", "message": "Profile reset to default", "profile": default.to_dict()}


@router.post("/{user_id}/learn")
def learn_from_content(user_id: str, req: LearnRequest) -> Dict[str, Any]:
    """Learn profile features from document text content."""
    learner = DocumentProfileLearner()
    features = learner.learn_from_content(
        content=req.content,
        domain=req.domain,
        document_id=req.document_id,
    )

    profile = _load_profile(user_id)
    profile_dict = profile.to_dict()
    merged = learner.merge_features_to_profile(profile_dict, features)

    updated = Profile.from_dict(merged)
    _save_profile(updated)

    return {
        "status": "ok",
        "message": f"Learned from document",
        "extracted_features": {
            "terms_count": len(features.get("frequent_terms", {})),
            "patterns_count": len(features.get("document_patterns", [])),
        },
        "profile": updated.to_dict(),
    }


@router.post("/{user_id}/learn-file")
def learn_from_file(user_id: str, req: LearnFileRequest) -> Dict[str, Any]:
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
    features = learner.learn_from_content(content=content, domain=req.domain, document_id=doc_id)

    profile = _load_profile(user_id)
    profile_dict = profile.to_dict()
    merged = learner.merge_features_to_profile(profile_dict, features)
    updated = Profile.from_dict(merged)
    _save_profile(updated)

    return {
        "status": "ok",
        "message": f"Learned from file: {file_path.name}",
        "profile": updated.to_dict(),
    }


# ========================================
# Knowledge CRUD
# ========================================

@router.post("/{user_id}/knowledge")
def add_knowledge(user_id: str, req: KnowledgeEntryRequest) -> Dict[str, Any]:
    """Add a condition-grouped knowledge entry. Auto-deduplicates by entity+conditions."""
    profile = _load_profile(user_id)
    entry = ConditionGroup(
        entity=req.entity,
        conditions=req.conditions,
        attributes=req.attributes,
        source=req.source,
    )
    entry_id = profile.add_knowledge(entry)
    _save_profile(profile)
    return {"status": "ok", "id": entry_id, "profile": profile.to_dict()}


@router.delete("/{user_id}/knowledge/{entry_id}")
def remove_knowledge(user_id: str, entry_id: str) -> Dict[str, Any]:
    """Remove a knowledge entry by ID."""
    profile = _load_profile(user_id)
    if not profile.remove_knowledge(entry_id):
        raise HTTPException(status_code=404, detail=f"Knowledge entry {entry_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}


@router.post("/{user_id}/knowledge/merge")
def merge_knowledge(user_id: str, req: KnowledgeMergeRequest) -> Dict[str, Any]:
    """Batch merge multiple knowledge entries. Returns count of new entries added."""
    profile = _load_profile(user_id)
    entries = [
        ConditionGroup(entity=e.entity, conditions=e.conditions, attributes=e.attributes, source=e.source)
        for e in req.entries
    ]
    added = profile.merge_knowledge(entries)
    _save_profile(profile)
    return {"status": "ok", "added": added, "total": len(profile.knowledge), "profile": profile.to_dict()}


@router.post("/{user_id}/knowledge/search")
def search_knowledge(user_id: str, req: KnowledgeSearchRequest) -> Dict[str, Any]:
    """Search knowledge entries by entity and optional conditions."""
    profile = _load_profile(user_id)
    results = profile.find_knowledge(req.entity, req.conditions)
    return {"status": "ok", "results": results, "count": len(results)}


# ========================================
# Principle CRUD
# ========================================

@router.post("/{user_id}/principles")
def add_principle(user_id: str, req: PrincipleRequest) -> Dict[str, Any]:
    """Add a compliance principle. Auto-deduplicates by name+dimension."""
    profile = _load_profile(user_id)
    principle = Principle(
        dimension=req.dimension,
        name=req.name,
        description=req.description,
        check_expression=req.check_expression,
        severity=req.severity,
        source=req.source,
    )
    pid = profile.add_principle(principle)
    _save_profile(profile)
    return {"status": "ok", "id": pid, "profile": profile.to_dict()}


@router.delete("/{user_id}/principles/{principle_id}")
def remove_principle(user_id: str, principle_id: str) -> Dict[str, Any]:
    """Remove a principle by ID."""
    profile = _load_profile(user_id)
    if not profile.remove_principle(principle_id):
        raise HTTPException(status_code=404, detail=f"Principle {principle_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}


# ========================================
# Preference CRUD
# ========================================

@router.post("/{user_id}/preferences")
def add_preference(user_id: str, req: PreferenceRequest) -> Dict[str, Any]:
    """Add a learned preference. Auto-deduplicates by category+dimension."""
    profile = _load_profile(user_id)
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


@router.delete("/{user_id}/preferences/{pref_id}")
def remove_preference(user_id: str, pref_id: str) -> Dict[str, Any]:
    """Remove a preference by ID."""
    profile = _load_profile(user_id)
    if not profile.remove_preference(pref_id):
        raise HTTPException(status_code=404, detail=f"Preference {pref_id} not found")
    _save_profile(profile)
    return {"status": "ok", "profile": profile.to_dict()}
