"""
Profile API - User profile management and document-based learning.

Endpoints:
- GET  /api/profile/{user_id}          — Get current profile
- POST /api/profile/{user_id}/learn     — Learn profile from document content
- POST /api/profile/{user_id}/learn-file — Learn profile from parsed document file
- PUT  /api/profile/{user_id}           — Update profile fields
- DELETE /api/profile/{user_id}         — Reset profile to default
"""
from typing import Any, Dict, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from app.shared.logging import get_logger
from app.models.profile import Profile
from app.services.document_profile_learner import DocumentProfileLearner
from app.config import settings

logger = get_logger(__name__)

router = APIRouter()

# Profile storage directory
PROFILES_DIR = Path(settings.DATA_DIR) / "profiles"


class LearnRequest(BaseModel):
    """Request body for learning profile from text content."""
    content: str = Field(..., min_length=10, description="Document text content")
    domain: str = Field(default="assembly", description="Domain: assembly/welding/coating")
    document_id: Optional[str] = Field(default=None, description="Source document ID")


class LearnFileRequest(BaseModel):
    """Request body for learning profile from a parsed document file."""
    file_path: str = Field(..., description="Path to parsed document JSON/text file")
    domain: str = Field(default="assembly", description="Domain: assembly/welding/coating")
    document_id: Optional[str] = Field(default=None, description="Source document ID override")


class ProfileUpdateRequest(BaseModel):
    """Request body for updating profile fields."""
    writing: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None
    ai_generated_summary: Optional[str] = None


def _get_profile_path(user_id: str) -> Path:
    """Get the JSON file path for a user's profile."""
    return PROFILES_DIR / f"{user_id}.json"


def _load_profile(user_id: str) -> Profile:
    """Load profile from JSON file, or return default."""
    path = _get_profile_path(user_id)
    if path.exists():
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return Profile.from_dict(data)
    # Return default profile
    return Profile(id=f"profile_{user_id}", user_id=user_id, domain="assembly")


def _save_profile(profile: Profile) -> None:
    """Save profile to JSON file."""
    import json
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = _get_profile_path(profile.user_id)
    path.write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/{user_id}")
def get_profile(user_id: str) -> Dict[str, Any]:
    """Get the current profile for a user."""
    profile = _load_profile(user_id)
    return {"status": "ok", "profile": profile.to_dict()}


@router.post("/{user_id}/learn")
def learn_from_content(user_id: str, req: LearnRequest) -> Dict[str, Any]:
    """
    Learn profile features from document text content.

    This is the main entry point: user selects content from a parsed
    document, posts it here, and the profile is updated.
    """
    learner = DocumentProfileLearner()
    features = learner.learn_from_content(
        content=req.content,
        domain=req.domain,
        document_id=req.document_id,
    )

    # Load existing profile and merge
    profile = _load_profile(user_id)
    profile_dict = profile.to_dict()
    merged = learner.merge_features_to_profile(profile_dict, features)

    # Save updated profile
    updated_profile = Profile.from_dict(merged)
    _save_profile(updated_profile)

    logger.info(
        "profile_learned",
        user_id=user_id,
        terms=len(features.get("frequent_terms", {})),
        document_id=req.document_id,
    )

    return {
        "status": "ok",
        "message": f"Learned {len(features.get('frequent_terms', {}))} terms from document",
        "extracted_features": {
            "terms_count": len(features.get("frequent_terms", {})),
            "patterns_count": len(features.get("document_patterns", [])),
            "style": {
                k: features[k]
                for k in ("preferred_sentence_length", "use_passive_voice", "include_caution_notes")
                if k in features
            },
        },
        "profile": updated_profile.to_dict(),
    }


@router.post("/{user_id}/learn-file")
def learn_from_file(user_id: str, req: LearnFileRequest) -> Dict[str, Any]:
    """
    Learn profile from a parsed document file on the server.

    Reads the file, extracts content, and runs the same learning pipeline.
    """
    file_path = Path(req.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    # Read file content
    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {e}")

    # If JSON, try to extract text content from common parsing formats
    content = raw
    if file_path.suffix == ".json":
        import json
        try:
            data = json.loads(raw)
            # Common parsed document structures
            if isinstance(data, dict):
                # MinerU format
                if "pages" in data:
                    texts = []
                    for page in data.get("pages", []):
                        for block in page.get("blocks", []):
                            texts.append(block.get("text", ""))
                    content = "\n".join(texts)
                # Simple content field
                elif "content" in data:
                    c = data["content"]
                    if isinstance(c, list):
                        content = "\n".join(str(item) for item in c)
                    else:
                        content = str(c)
                elif "text" in data:
                    content = data["text"]
        except json.JSONDecodeError:
            pass  # Use raw content

    doc_id = req.document_id or file_path.stem

    learner = DocumentProfileLearner()
    features = learner.learn_from_content(
        content=content,
        domain=req.domain,
        document_id=doc_id,
    )

    profile = _load_profile(user_id)
    profile_dict = profile.to_dict()
    merged = learner.merge_features_to_profile(profile_dict, features)

    updated_profile = Profile.from_dict(merged)
    _save_profile(updated_profile)

    return {
        "status": "ok",
        "message": f"Learned from file: {file_path.name}",
        "extracted_features": {
            "terms_count": len(features.get("frequent_terms", {})),
            "patterns_count": len(features.get("document_patterns", [])),
        },
        "profile": updated_profile.to_dict(),
    }


@router.put("/{user_id}")
def update_profile(user_id: str, req: ProfileUpdateRequest) -> Dict[str, Any]:
    """Manually update profile fields."""
    profile = _load_profile(user_id)
    profile_dict = profile.to_dict()

    if req.writing:
        profile_dict["writing"].update(req.writing)
    if req.review:
        profile_dict["review"].update(req.review)
    if req.preferences:
        profile_dict.setdefault("preferences", {}).update(req.preferences)
    if req.ai_generated_summary is not None:
        profile_dict["ai_generated_summary"] = req.ai_generated_summary

    updated_profile = Profile.from_dict(profile_dict)
    _save_profile(updated_profile)

    return {"status": "ok", "profile": updated_profile.to_dict()}


@router.delete("/{user_id}")
def reset_profile(user_id: str) -> Dict[str, Any]:
    """Reset profile to default (deletes learned data)."""
    path = _get_profile_path(user_id)
    if path.exists():
        path.unlink()

    default_profile = Profile(id=f"profile_{user_id}", user_id=user_id, domain="assembly")
    return {"status": "ok", "message": "Profile reset to default", "profile": default_profile.to_dict()}
