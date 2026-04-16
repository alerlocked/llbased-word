"""
MemoryService - 记忆管理服务

管理会话记忆（跨会话持久化），用于 LLM 上下文注入。
支持按时间加载（load_recent_memory）和按语义检索（load_relevant_memory）。
"""
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import re

from app.shared.logging import get_logger

logger = get_logger(__name__)


class MemoryService:
    """记忆管理服务
    
    职责：
    - 保存会话摘要
    - 加载最近的记忆
    - 清理旧记忆
    """
    
    def __init__(self, memory_dir: str):
        """初始化记忆服务
        
        Args:
            memory_dir: 记忆目录 (.project-meta/memory/)
        """
        self.memory_dir = Path(memory_dir)
        
        if not self.memory_dir.exists():
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[记忆服务] 已创建记忆目录: {self.memory_dir}")
    
    def save_summary(self, session_id: str, summary: str, entities: Optional[List[str]] = None) -> bool:
        """保存会话摘要
        
        文件路径: {memory_dir}/{session_id}.md
        
        Args:
            session_id: 会话 ID
            summary: 摘要内容
            entities: 关键实体列表（可选）
            
        Returns:
            是否保存成功
        """
        memory_path = self.memory_dir / f"{session_id}.md"
        
        try:
            # 构建记忆内容
            content_lines = [
                "# 会话摘要",
                "",
                "## 时间",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "",
                "## 摘要",
                summary
            ]
            
            # 添加关键实体
            if entities:
                content_lines.extend([
                    "",
                    "## 关键实体"
                ])
                for entity in entities:
                    content_lines.append(f"- {entity}")
            
            content = "\n".join(content_lines)
            
            with open(memory_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            logger.info(f"[记忆服务] 保存摘要成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"[记忆服务] 保存摘要失败: {session_id}, {e}")
            return False
    
    def load_recent_memory(self, max_tokens: int = 1000) -> str:
        """加载最近的记忆（用于新会话上下文）
        
        逻辑：
        1. 按修改时间倒序排列所有记忆文件
        2. 依次加载，直到达到 max_tokens
        3. 合并为一个上下文字符串
        
        Args:
            max_tokens: 最大 token 数量
            
        Returns:
            合并后的记忆上下文
        """
        if not self.memory_dir.exists():
            return ""
        
        # 获取所有记忆文件，按修改时间倒序
        memory_files = sorted(
            self.memory_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not memory_files:
            return ""
        
        memory_parts = []
        used_tokens = 0
        
        for memory_file in memory_files:
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 估算 token
                content_tokens = self._estimate_tokens(content)
                
                # 检查是否超过限制
                if used_tokens + content_tokens > max_tokens:
                    # 尝试截断
                    remaining_tokens = max_tokens - used_tokens
                    if remaining_tokens > 100:  # 至少保留 100 tokens
                        truncated_content = self._truncate_to_tokens(content, remaining_tokens)
                        memory_parts.append(truncated_content)
                        used_tokens += remaining_tokens
                    break
                
                memory_parts.append(content)
                used_tokens += content_tokens
                
            except Exception as e:
                logger.error(f"[记忆服务] 读取记忆文件失败: {memory_file}, {e}")
                continue
        
        if not memory_parts:
            return ""
        
        # 合并记忆
        merged_memory = "\n\n---\n\n".join(memory_parts)
        logger.info(f"[记忆服务] 加载最近记忆完成: {len(memory_parts)} 个文件, {used_tokens} tokens")
        return merged_memory
    
    def get_session_memory(self, session_id: str) -> Optional[str]:
        """获取指定会话的记忆
        
        Args:
            session_id: 会话 ID
            
        Returns:
            记忆内容，如果不存在则返回 None
        """
        memory_path = self.memory_dir / f"{session_id}.md"
        
        if not memory_path.exists():
            return None
        
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"[记忆服务] 读取会话记忆失败: {session_id}, {e}")
            return None
    
    def clear_old_memories(self, keep_count: int = 10) -> int:
        """清理旧记忆，保留最近 N 个
        
        Args:
            keep_count: 保留的记忆数量
            
        Returns:
            删除的记忆数量
        """
        if not self.memory_dir.exists():
            return 0
        
        # 获取所有记忆文件，按修改时间倒序
        memory_files = sorted(
            self.memory_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # 保留前 N 个，删除其余
        files_to_delete = memory_files[keep_count:]
        deleted_count = 0
        
        for file_path in files_to_delete:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"[记忆服务] 删除记忆文件失败: {file_path}, {e}")
        
        logger.info(f"[记忆服务] 清理完成: 删除 {deleted_count} 个记忆, 保留 {len(memory_files) - deleted_count} 个")
        return deleted_count

    def load_relevant_memory(
        self, query: str, max_tokens: int = 1000, top_k: int = 5
    ) -> str:
        """
        Load memory relevant to a query using semantic search.

        Falls back to load_recent_memory if embedding is unavailable.

        Args:
            query: Query text to find relevant memories
            max_tokens: Maximum tokens to return
            top_k: Number of candidate memories to consider

        Returns:
            Relevant memory context string
        """
        if not self.memory_dir.exists():
            return ""

        memory_files = sorted(
            self.memory_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not memory_files:
            return ""

        # Load candidate files
        candidates: List[Dict[str, Any]] = []
        for mf in memory_files[:top_k * 3]:
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

    def index_memories_to_chroma(self) -> Dict[str, int]:
        """
        Index all memory files into ChromaDB for persistent semantic search.

        Returns:
            Summary with indexed count
        """
        if not self.memory_dir.exists():
            return {"indexed": 0}

        try:
            from app.tools.vector_store import VectorStore

            vs = VectorStore({"collection_name": "session_memory"})
            memory_files = list(self.memory_dir.glob("*.md"))

            documents = []
            metadatas = []
            for mf in memory_files:
                content = mf.read_text(encoding="utf-8")
                documents.append({"id": mf.stem, "text": content})
                metadatas.append({
                    "source": "memory",
                    "session_id": mf.stem,
                    "mtime": datetime.fromtimestamp(mf.stat().st_mtime).isoformat(),
                })

            if documents:
                import asyncio
                asyncio.get_event_loop().run_until_complete(
                    vs.add_documents(documents, metadatas)
                )

            logger.info("memories_indexed", count=len(documents))
            return {"indexed": len(documents)}

        except Exception as e:
            logger.error("memory_indexing_failed", error=str(e))
            return {"indexed": 0, "error": str(e)}
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数量
        
        中文按 1.5 tokens/字符，英文按 0.25 tokens/字符
        """
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.25)
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """截断文本到指定 token 数量
        
        Args:
            text: 原始文本
            max_tokens: 最大 token 数量
            
        Returns:
            截断后的文本
        """
        # 估算字符数（保守估计）
        # 中文 1.5 tokens/字符 → 1 token ≈ 0.67 字符
        # 英文 0.25 tokens/字符 → 1 token ≈ 4 字符
        # 取中间值：1 token ≈ 2 字符
        estimated_chars = max_tokens * 2
        
        if len(text) <= estimated_chars:
            return text
        
        truncated = text[:estimated_chars]
        # 尝试在句子边界截断
        last_period = max(
            truncated.rfind("。"),
            truncated.rfind("！"),
            truncated.rfind("？"),
            truncated.rfind("."),
            truncated.rfind("\n")
        )
        
        if last_period > estimated_chars * 0.7:
            truncated = truncated[:last_period + 1]
        
        return truncated + "\n\n[...已截断...]"
