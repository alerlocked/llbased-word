"""
Preference Learner — Analyze user events and extract writing preferences via LLM.

Reads user_event logs, summarizes patterns, and produces a preference profile
that can be injected into WritingAgent prompts.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.shared.logging import get_logger

logger = get_logger(__name__)

# Default profile path
PROFILE_FILENAME = "preference_profile.json"


class PreferenceLearner:
    """Analyze user behavior events and extract writing style preferences."""

    def __init__(self, data_dir: Path | str | None = None):
        if data_dir is None:
            from app.config import settings
            self._data_dir = settings.DATA_DIR
        else:
            self._data_dir = Path(data_dir)
        self._profile_path = self._data_dir / PROFILE_FILENAME

    # -- Event recording -----------------------------------------------------

    @staticmethod
    def record_event(
        db: Session,
        event_type: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        content_before: Optional[str] = None,
        content_after: Optional[str] = None,
        ai_suggestion: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
    ) -> int:
        """Record a user action event.

        Returns the event ID.
        """
        from app.models.database import UserEvent

        event = UserEvent(
            user_id=user_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            content_before=content_before,
            content_after=content_after,
            ai_suggestion=ai_suggestion,
            session_id=session_id,
        )
        db.add(event)
        db.commit()
        return event.id

    # -- Preference extraction -----------------------------------------------

    def load_profile(self) -> Dict[str, Any]:
        """Load existing preference profile from disk."""
        if self._profile_path.exists():
            try:
                return json.loads(self._profile_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"[偏好] 加载配置文件失败: {e}")
        return self._default_profile()

    def save_profile(self, profile: Dict[str, Any]) -> None:
        """Persist preference profile to disk."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"[偏好] 配置文件已保存: {self._profile_path}")

    async def analyze_and_update(
        self,
        db: Session,
        user_id: str = "default",
        days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze recent user events and update preference profile.

        This uses LLM to extract patterns from user edit history.

        Returns:
            Updated preference profile dict.
        """
        from app.models.database import UserEvent

        # Fetch recent events
        cutoff = datetime.utcnow() - timedelta(days=days)
        events = db.query(UserEvent).filter(
            UserEvent.user_id == user_id,
            UserEvent.created_at >= cutoff,
        ).order_by(UserEvent.created_at.desc()).limit(100).all()

        if not events:
            logger.info(f"[偏好] 无近期事件, user={user_id}")
            return self.load_profile()

        # Build event summary for LLM analysis
        summary = self._build_event_summary(events)

        # Use LLM to extract preferences
        preferences = await self._llm_extract_preferences(summary)

        # Merge with existing profile
        profile = self.load_profile()
        profile = self._merge_preferences(profile, preferences, events)
        profile["last_updated"] = datetime.utcnow().isoformat()
        profile["event_count"] = len(events)

        self.save_profile(profile)
        return profile

    def get_preference_text(self, user_id: str = "default") -> str:
        """Get a formatted text block of user preferences for prompt injection.

        Returns empty string if no preferences are learned yet.
        """
        profile = self.load_profile()
        if profile.get("event_count", 0) < 3:
            return ""

        lines = ["## 用户写作偏好\n"]

        vocab = profile.get("vocabulary", {})
        if vocab:
            lines.append("### 用词偏好")
            for preferred, avoided in vocab.items():
                if avoided:
                    lines.append(f"- 使用「{preferred}」而非「{avoided}」")
                else:
                    lines.append(f"- 偏好使用「{preferred}」")

        style = profile.get("style", {})
        if style:
            lines.append("\n### 写作风格")
            if style.get("detail_level"):
                lines.append(f"- 详细程度: {style['detail_level']}")
            if style.get("sentence_style"):
                lines.append(f"- 句式风格: {style['sentence_style']}")

        term_mappings = profile.get("term_mappings", {})
        if term_mappings:
            lines.append("\n### 术语映射")
            for key, val in term_mappings.items():
                lines.append(f"- {key} → {val}")

        return "\n".join(lines) if len(lines) > 2 else ""

    # -- internal helpers ----------------------------------------------------

    def _default_profile(self) -> Dict[str, Any]:
        return {
            "vocabulary": {},
            "style": {},
            "term_mappings": {},
            "event_count": 0,
            "last_updated": None,
        }

    def _build_event_summary(self, events) -> str:
        """Build a text summary of events for LLM analysis."""
        parts = []
        for e in events[:50]:  # Cap at 50 events
            line = f"[{e.event_type}]"
            if e.target_type:
                line += f" target={e.target_type}"
            if e.content_before and e.content_after:
                line += f"\n  修改前: {e.content_before[:200]}"
                line += f"\n  修改后: {e.content_after[:200]}"
            if e.ai_suggestion and e.event_type in ("accept", "reject"):
                line += f"\n  AI建议: {e.ai_suggestion[:200]}"
                line += f"  用户操作: {e.event_type}"
            parts.append(line)
        return "\n\n".join(parts)

    async def _llm_extract_preferences(self, summary: str) -> Dict[str, Any]:
        """Use LLM to extract writing preferences from event summary."""
        from app.services.llm_service import llm_service

        system_msg = (
            "你是一位写作风格分析专家。请分析以下工艺师的编辑操作记录，"
            "提取其写作偏好。输出 JSON 格式：\n"
            "{\n"
            '  "vocabulary": {"偏好词": "避免词", ...},\n'
            '  "style": {"detail_level": "详细/简洁/适中", "sentence_style": "描述"},\n'
            '  "term_mappings": {"非标准术语": "标准术语", ...}\n'
            "}\n"
            "只输出有依据的偏好，不要猜测。"
        )

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"编辑记录：\n{summary[:3000]}"},
            ],
            temperature=0.2,
            max_tokens=1000,
            tier="fast",
        )

        if result["status"] != "success":
            return {}

        try:
            text = result["content"].strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            logger.warning("[偏好] LLM 输出非 JSON，跳过偏好提取")
            return {}

    def _merge_preferences(
        self,
        profile: Dict[str, Any],
        new_prefs: Dict[str, Any],
        events,
    ) -> Dict[str, Any]:
        """Merge newly extracted preferences into existing profile."""
        # Vocabulary: new entries override old ones
        if "vocabulary" in new_prefs:
            profile["vocabulary"].update(new_prefs["vocabulary"])

        # Style: take latest if changed
        if "style" in new_prefs:
            profile["style"].update(new_prefs["style"])

        # Term mappings: merge
        if "term_mappings" in new_prefs:
            profile["term_mappings"].update(new_prefs["term_mappings"])

        return profile
