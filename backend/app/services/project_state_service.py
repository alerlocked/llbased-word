"""Per-project rolling working-state service (session continuity).

State = task-level rolling summary of what the project is currently working on
(current task, focus chapters, recent intents, user wording preferences).
Distinct from MemoryService: state is rolling-overwrite JSON injected on every
new-session start; memory is append-only markdown summaries recalled by keyword.

Storage: {PROJECT_STATE_DIR}/{project_id}.json, atomic write (tmp + os.replace,
same pattern as MemoryService.save_summary). Future user dimension = add a path
level ({user_id}/{project_id}/) at the call site, not here.
"""
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.shared.logging import get_logger

logger = get_logger(__name__)

# Chapter codes like G25a / G4a / A1 / K3b appearing in user input.
# ASCII-only lookarounds (NOT \b): Python \w includes CJK, so \b never fires
# between a Chinese char and an ASCII letter — "修改G25a第3行" would extract
# nothing. Lookarounds also reject letter-wrapped tokens (AG25a, RGB25).
_CHAPTER_CODE_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]\d{1,2}[a-z]?)(?![A-Za-z0-9])")

# Preference-signal keywords in user input → append to user_preferences
_PREFERENCE_SIGNALS = ("偏好", "以后都", "统一", "都改成", "一律", "默认用")


class ProjectStateService:
    """Rolling per-project working state with atomic JSON persistence."""

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, project_id: int | str) -> Path:
        return self.state_dir / f"{project_id}.json"

    def load(self, project_id: int | str) -> Dict[str, Any]:
        """Load state dict; {} when missing or corrupt (logged, not raised)."""
        path = self._path(project_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("project_state_load_failed", project_id=project_id, error=str(e))
            return {}

    def update(self, project_id: int | str, **fields: Any) -> bool:
        """Merge fields into the rolling state and persist atomically."""
        from app.config import settings

        with self._lock:
            state = self.load(project_id)
            state.update(fields)
            # enforce rolling caps
            state["current_task"] = (state.get("current_task") or "")[: settings.STATE_TASK_MAX_CHARS]
            state["focus_chapters"] = (state.get("focus_chapters") or [])[-settings.STATE_FOCUS_CHAPTERS_KEEP:]
            state["recent_intents"] = (state.get("recent_intents") or [])[-settings.STATE_RECENT_INTENTS_KEEP:]
            state["project_id"] = project_id
            state["updated_at"] = datetime.now().isoformat(timespec="seconds")
            return self._atomic_write(self._path(project_id), state)

    def update_from_turn(
        self,
        project_id: int | str,
        session_id: Optional[str],
        user_input: str,
        intent_type: Optional[str],
        focus_chapters: Optional[List[str]] = None,
        output_summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Roll the state forward after one conversation turn.

        Composition happens INSIDE the lock off a single load — two loads
        (compose, then merge) had a lost-update window between them.
        output_summary (optional): {"chapters": [{"code","title","rows"}],
        "warnings_count": int} — rolling last-output snapshot (summary level;
        full data lives in the editor), so later turns can reference
        "刚才生成的那篇" without re-uploading.
        """
        from app.config import settings

        with self._lock:
            existing = self.load(project_id)

            if session_id:
                existing["last_session_id"] = session_id
            if user_input:
                existing["current_task"] = user_input.strip()
            if output_summary:
                existing["last_output"] = {
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    **output_summary,
                }
            intents = list(existing.get("recent_intents") or [])
            if intent_type and intent_type not in intents[-1:]:
                intents.append(intent_type)
            existing["recent_intents"] = intents

            chapters = list(focus_chapters or [])
            if user_input:
                chapters.extend(_CHAPTER_CODE_RE.findall(user_input))
            seen = set()
            ordered = [c for c in chapters if not (c in seen or seen.add(c))]
            merged = list(existing.get("focus_chapters") or []) + ordered
            seen2 = set()
            existing["focus_chapters"] = [
                c for c in merged if not (c in seen2 or seen2.add(c))
            ]

            if user_input and any(s in user_input for s in _PREFERENCE_SIGNALS):
                prefs = existing.get("user_preferences") or ""
                existing["user_preferences"] = (
                    prefs + ("；" if prefs else "") + user_input.strip()
                )[-200:]

            # rolling caps + persist (same invariants as update())
            existing["current_task"] = (existing.get("current_task") or "")[: settings.STATE_TASK_MAX_CHARS]
            existing["focus_chapters"] = (existing.get("focus_chapters") or [])[-settings.STATE_FOCUS_CHAPTERS_KEEP:]
            existing["recent_intents"] = (existing.get("recent_intents") or [])[-settings.STATE_RECENT_INTENTS_KEEP:]
            existing["project_id"] = project_id
            existing["updated_at"] = datetime.now().isoformat(timespec="seconds")
            return self._atomic_write(self._path(project_id), existing)

    def render_context_block(self, state: Dict[str, Any]) -> str:
        """Render a compact '## 项目当前工作状态' prompt block; '' when empty."""
        if not state:
            return ""
        lines: List[str] = []
        if state.get("current_task"):
            lines.append(f"- 当前任务: {state['current_task']}")
        if state.get("focus_chapters"):
            lines.append(f"- 正在编辑: {'、'.join(state['focus_chapters'])}")
        if state.get("recent_intents"):
            lines.append(f"- 最近意图: {'、'.join(state['recent_intents'][-3:])}")
        last_output = state.get("last_output") or {}
        if last_output.get("chapters"):
            codes = "、".join(c.get("code", "") for c in last_output["chapters"][:8])
            extra = f" 等共 {len(last_output['chapters'])} 章" if len(last_output["chapters"]) > 8 else ""
            warn = f"，{last_output.get('warnings_count', 0)} 处警告" if last_output.get("warnings_count") else ""
            lines.append(f"- 最近产出: 已生成 {codes}{extra}{warn}（{last_output.get('updated_at', '')}）")
        if state.get("user_preferences"):
            lines.append(f"- 用户措辞偏好: {state['user_preferences']}")
        if not lines:
            return ""
        return "## 项目当前工作状态（接续上一会话）\n" + "\n".join(lines)

    @staticmethod
    def _atomic_write(path: Path, data: Dict[str, Any]) -> bool:
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            import os
            os.replace(tmp, path)
            return True
        except OSError as e:
            logger.error("project_state_write_failed", path=str(path), error=str(e))
            return False


# Module-level singleton (mirror llm_service / memory_service pattern)
from app.config import settings  # noqa: E402

project_state_service = ProjectStateService(settings.PROJECT_STATE_DIR)
