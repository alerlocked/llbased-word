"""
MemoryService - session memory management

Manages cross-session memory for LLM context injection.
Supports time-based loading (load_recent_memory) and
semantic retrieval (load_relevant_memory).
"""
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import re
import os
import threading

from app.shared.logging import get_logger

logger = get_logger(__name__)


def _safe_mtime(p: Path) -> float:
    """Get mtime with race-condition protection."""
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


class MemoryService:
    """Session memory management service

    Responsibilities:
    - Save session summaries (async via LLM)
    - Load recent / relevant memories for context injection
    - Auto-cleanup when file count exceeds threshold
    """

    def __init__(self, memory_dir: str):
        self.memory_dir = Path(memory_dir)

        if not self.memory_dir.exists():
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[记忆服务] 已创建记忆目录: {self.memory_dir}")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_summary(
        self,
        session_id: str,
        summary: str,
        entities: Optional[List[str]] = None,
    ) -> bool:
        """Save session summary with atomic write.

        File path: {memory_dir}/{timestamp}_{session_id}.md

        Returns:
            True if saved successfully.
        """
        memory_path = self.memory_dir / f"{session_id}.md"

        try:
            # Build content
            content_lines = [
                "# 会话摘要",
                "",
                "## 时间",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "",
                "## 摘要",
                summary,
            ]

            if entities:
                content_lines.extend(["", "## 关键实体"])
                for entity in entities:
                    content_lines.append(f"- {entity}")

            content = "\n".join(content_lines)

            # Atomic write: temp file → rename
            tmp_path = memory_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, memory_path)

            logger.info(f"[记忆服务] 保存摘要成功: {session_id}")

            # Auto-cleanup
            try:
                from app.config import settings
                self._auto_cleanup(settings.MEMORY_KEEP_COUNT)
            except Exception:
                self._auto_cleanup(20)

            return True

        except Exception as e:
            logger.error(f"[记忆服务] 保存摘要失败: {session_id}, {e}")
            return False

    def save_summary_async(
        self,
        session_id: str,
        user_input: str,
        ai_response: str,
    ) -> None:
        """Fire-and-forget: call LLM to generate summary, then save.

        Returns immediately; summary generation runs in a background thread.
        Failures are silently logged and do not affect the caller.
        """
        def _worker() -> None:
            try:
                import asyncio
                from app.services.llm_service import llm_service
                from app.config import settings

                prompt = (
                    "请将以下对话浓缩为1-2句话的摘要，并列出涉及的关键实体（零件名、"
                    "材料、工艺类型等）。\n\n"
                    f"用户: {user_input}\n\n"
                    f"助手: {ai_response}\n\n"
                    "请用以下格式输出:\n"
                    "摘要: ...\n"
                    "实体: 实体1, 实体2, ..."
                )

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(
                        llm_service.generate_text(
                            prompt=prompt,
                            temperature=0.3,
                            max_tokens=settings.MEMORY_SUMMARY_MAX_TOKENS,
                            tier="simple",  # Summarization → lightweight model
                        )
                    )
                finally:
                    loop.close()

                if result.get("status") != "error":
                    text = result.get("content") or ""
                    if not isinstance(text, str):
                        text = ""
                    summary, entities = self._parse_summary(text)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    mem_id = f"{ts}_{session_id[:8]}"
                    self.save_summary(mem_id, summary, entities)
                else:
                    logger.warning(
                        f"[记忆服务] LLM摘要生成失败: {result.get('error', 'unknown')}"
                    )
            except Exception as e:
                logger.warning(f"[记忆服务] 异步摘要保存失败: {e}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_recent_memory(self, max_tokens: int = 1000) -> str:
        """Load most recent memories within token budget."""
        if not self.memory_dir.exists():
            return ""

        memory_files = sorted(
            self.memory_dir.glob("*.md"),
            key=_safe_mtime,
            reverse=True,
        )

        if not memory_files:
            return ""

        memory_parts: List[str] = []
        used_tokens = 0

        for memory_file in memory_files:
            try:
                content = memory_file.read_text(encoding="utf-8")
                content_tokens = self._estimate_tokens(content)

                if used_tokens + content_tokens > max_tokens:
                    remaining_tokens = max_tokens - used_tokens
                    if remaining_tokens > 100:
                        memory_parts.append(
                            self._truncate_to_tokens(content, remaining_tokens)
                        )
                        used_tokens += remaining_tokens
                    break

                memory_parts.append(content)
                used_tokens += content_tokens

            except Exception as e:
                logger.error(f"[记忆服务] 读取记忆文件失败: {memory_file}, {e}")
                continue

        if not memory_parts:
            return ""

        merged = "\n\n---\n\n".join(memory_parts)
        logger.info(
            f"[记忆服务] 加载最近记忆完成: {len(memory_parts)} 个文件, {used_tokens} tokens"
        )
        return merged

    def load_relevant_memory(
        self, query: str, max_tokens: int = 1000, top_k: int = 5
    ) -> str:
        """Load memory relevant to a query using semantic search.

        Falls back to load_recent_memory if embedding is unavailable.
        """
        if not self.memory_dir.exists():
            return ""

        memory_files = sorted(
            self.memory_dir.glob("*.md"),
            key=_safe_mtime,
            reverse=True,
        )
        if not memory_files:
            return ""

        candidates: List[Dict[str, Any]] = []
        for mf in memory_files[: top_k * 3]:
            try:
                content = mf.read_text(encoding="utf-8")
                candidates.append({"path": mf, "content": content})
            except Exception:
                continue

        if not candidates:
            return ""

        # Try semantic ranking
        try:
            from app.services.context_engineering import (
                calculate_embedding,
                calculate_similarity,
            )

            query_embedding = calculate_embedding(query)
            if query_embedding:
                scored: List[Dict[str, Any]] = []
                for cand in candidates:
                    emb = calculate_embedding(cand["content"][:500])
                    if emb:
                        sim = calculate_similarity(query_embedding, emb)
                        scored.append({**cand, "score": sim})
                    else:
                        scored.append({**cand, "score": 0.0})

                scored.sort(key=lambda x: x["score"], reverse=True)
                candidates = scored[:top_k]
        except Exception as e:
            logger.warning("semantic_memory_fallback", error=str(e))
            candidates = candidates[:top_k]

        # Build result within token budget
        memory_parts: List[str] = []
        used_tokens = 0
        for cand in candidates:
            tokens = self._estimate_tokens(cand["content"])
            if used_tokens + tokens > max_tokens:
                remaining = max_tokens - used_tokens
                if remaining > 100:
                    memory_parts.append(
                        self._truncate_to_tokens(cand["content"], remaining)
                    )
                break
            memory_parts.append(cand["content"])
            used_tokens += tokens

        if not memory_parts:
            return ""

        result = "\n\n---\n\n".join(memory_parts)
        logger.info("relevant_memory_loaded", parts=len(memory_parts), tokens=used_tokens)
        return result

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def clear_old_memories(self, keep_count: int = 10) -> int:
        """Delete old memories, keeping the most recent *keep_count*."""
        if not self.memory_dir.exists():
            return 0

        memory_files = sorted(
            self.memory_dir.glob("*.md"),
            key=_safe_mtime,
            reverse=True,
        )

        files_to_delete = memory_files[keep_count:]
        deleted_count = 0

        for file_path in files_to_delete:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"[记忆服务] 删除记忆文件失败: {file_path}, {e}")

        logger.info(
            f"[记忆服务] 清理完成: 删除 {deleted_count} 个, "
            f"保留 {len(memory_files) - deleted_count} 个"
        )
        return deleted_count

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count.

        Chinese: 1.5 tokens/char, English: 0.25 tokens/char.
        """
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.25)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within *max_tokens*.

        Uses _estimate_tokens logic to find the safe char boundary:
        Mixed Chinese/English text is conservatively estimated at ~1 token/char.
        """
        if self._estimate_tokens(text) <= max_tokens:
            return text

        # Conservative: 1 token ≈ 1 char for mixed Chinese/English
        estimated_chars = max_tokens

        if len(text) <= estimated_chars:
            return text

        truncated = text[:estimated_chars]
        # Try to truncate at sentence boundary
        last_period = max(
            truncated.rfind("\u3002"),  # 。
            truncated.rfind("\uff01"),  # ！
            truncated.rfind("\uff1f"),  # ？
            truncated.rfind("."),
            truncated.rfind("\n"),
        )

        if last_period > estimated_chars * 0.7:
            truncated = truncated[: last_period + 1]

        return truncated + "\n\n[...已截断...]"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auto_cleanup(self, keep_count: int) -> None:
        """Auto-cleanup if file count exceeds keep_count."""
        try:
            count = len(list(self.memory_dir.glob("*.md")))
            if count > keep_count:
                self.clear_old_memories(keep_count)
        except Exception as e:
            logger.warning(f"[记忆服务] 自动清理失败: {e}")

    @staticmethod
    def _parse_summary(text: str) -> tuple[str, List[str]]:
        """Parse LLM summary output into (summary, entities)."""
        summary = ""
        entities: List[str] = []

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("摘要:") or line.startswith("摘要："):
                summary = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            elif line.startswith("实体:") or line.startswith("实体："):
                ent_str = line.split(":", 1)[-1].split("：", 1)[-1].strip()
                entities = [e.strip() for e in ent_str.split(",") if e.strip()]

        if not summary:
            summary = text.strip()[:200]

        return summary, entities
