"""
LLMContextService - LLM 上下文管理服务

统一入口，组合 4 层上下文：System + Profile + Memory + 检索层
"""
from typing import Dict, Tuple, Optional, List
from pathlib import Path
import re
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.services.context_service import ContextService
from app.services.memory_service import MemoryService
from app.services.hierarchical_context import HierarchicalContext


class LLMContextService:
    """LLM 上下文管理服务
    
    4 层架构：
    - Layer 0: System（系统提示 + 任务说明）
    - Layer 1: Profile（用户画像 - 静态配置）
    - Layer 2: Memory（对话摘要 + 跨会话记忆）
    - Layer 3: 检索层（HierarchicalContext 素材检索）
    
    Token 预算分配（8K 窗口）：
    - System: 500
    - Profile: 300
    - Memory: 1000
    - 检索层: 3000
    - 预留（用户输入 + 回复）: 3200
    """
    
    # 默认 token 预算分配
    DEFAULT_BUDGET = {
        "system": 500,
        "profile": 300,
        "memory": 1000,
        "retrieval": 3000,
        "reserved": 3200
    }
    
    def __init__(self, base_path: str, memory_dir: str, data_dir: str):
        """初始化上下文服务
        
        Args:
            base_path: 项目根目录
            memory_dir: 记忆目录 (.project-meta/memory/)
            data_dir: 数据目录 (data/exports_html/)
        """
        from pathlib import Path
        self.base_path = Path(base_path)
        self.context_service = ContextService(base_path=self.base_path)
        self.memory_service = MemoryService(memory_dir)
        self.hierarchical_context = HierarchicalContext(data_dir)
        
        # Token 使用情况
        self._token_usage: Dict[str, int] = {
            "system": 0,
            "profile": 0,
            "memory": 0,
            "retrieval": 0,
            "total": 0
        }
        
        logger.info(
            f"[上下文服务] 初始化完成: "
            f"profile_dir={profile_dir}, memory_dir={memory_dir}, data_dir={data_dir}"
        )
    
    def build_context(
        self,
        query: str,
        session_id: str,
        max_tokens: int = 8000,
        profile_name: str = "default"
    ) -> Tuple[str, Dict[str, int]]:
        """构建完整上下文
        
        Args:
            query: 用户查询
            session_id: 会话 ID
            max_tokens: 最大 token 数量
            profile_name: 画像名称
            
        Returns:
            (context_text, token_breakdown)
            token_breakdown: {"system": 500, "profile": 300, "memory": 800, "rag": 2000}
        """
        logger.info(f"[上下文服务] 开始构建上下文: session={session_id}, query={query[:50]}")
        
        # 计算预算（按比例缩放）
        budget = self._calculate_budget(max_tokens)
        
        context_parts = []
        token_breakdown = {
            "system": 0,
            "profile": 0,
            "memory": 0,
            "retrieval": 0
        }
        
        # Layer 0: System
        system_context = self._build_system_context()
        system_tokens = self._estimate_tokens(system_context)
        
        if system_tokens > budget["system"]:
            system_context = self._truncate_to_tokens(system_context, budget["system"])
            system_tokens = budget["system"]
            logger.warning(f"[上下文服务] System 层被截断")
        
        context_parts.append(system_context)
        token_breakdown["system"] = system_tokens
        
        # Layer 1: Profile (通过 ContextService 加载)
        profile = self.context_service.load_profile(user_id=profile_name, domain="assembly")
        profile_context = profile.to_prompt_context() if hasattr(profile, 'to_prompt_context') else str(profile)
        profile_tokens = self._estimate_tokens(profile_context)
        
        if profile_tokens > budget["profile"]:
            profile_context = self._truncate_to_tokens(profile_context, budget["profile"])
            profile_tokens = budget["profile"]
            logger.warning(f"[上下文服务] Profile 层被截断")
        
        if profile_context:
            context_parts.append(f"\n# 用户画像\n\n{profile_context}")
        token_breakdown["profile"] = profile_tokens
        
        # Layer 2: Memory
        memory_context = self.memory_service.load_recent_memory(budget["memory"])
        memory_tokens = self._estimate_tokens(memory_context)
        
        if memory_context:
            context_parts.append(f"\n# 历史记忆\n\n{memory_context}")
        token_breakdown["memory"] = memory_tokens
        
        # Layer 3: 检索层
        # 计算剩余预算
        used_tokens = sum(token_breakdown.values())
        rag_budget = min(budget["rag"], max_tokens - used_tokens - budget["reserved"])
        
        if rag_budget > 0:
            # 设置 HierarchicalContext 的 token 限制
            self.hierarchical_context.set_max_tokens(rag_budget)
            
            # 构建 RAG 上下文
            rag_context = self.hierarchical_context.build_context(
                query=query,
                session_id=session_id,
                max_tokens=rag_budget
            )
            
            rag_tokens = self._estimate_tokens(rag_context)
            
            if rag_context:
                context_parts.append(f"\n# 参考资料\n\n{rag_context}")
            token_breakdown["retrieval"] = rag_tokens
        
        # 合并上下文
        final_context = "\n\n---\n\n".join(context_parts)
        total_tokens = sum(token_breakdown.values())
        
        # 更新 token 使用情况
        self._token_usage = {
            **token_breakdown,
            "total": total_tokens
        }
        
        logger.info(
            f"[上下文服务] 上下文构建完成: "
            f"total={total_tokens} tokens, "
            f"breakdown={token_breakdown}"
        )
        
        return final_context, token_breakdown
    
    def save_memory(
        self,
        session_id: str,
        summary: str,
        entities: Optional[List[str]] = None
    ) -> bool:
        """保存当前会话摘要到记忆系统
        
        Args:
            session_id: 会话 ID
            summary: 摘要内容
            entities: 关键实体列表（可选）
            
        Returns:
            是否保存成功
        """
        return self.memory_service.save_summary(session_id, summary, entities)
    
    def get_token_usage(self) -> Dict[str, int]:
        """获取当前 token 使用情况
        
        Returns:
            {"system": 500, "profile": 300, "memory": 800, "rag": 2000, "total": 3600}
        """
        return self._token_usage.copy()
    
    def _build_system_context(self) -> str:
        """构建 System 层上下文
        
        Returns:
            System 提示文本
        """
        return """# 系统提示

你是一个专业的工艺文件编辑助手，擅长：
- 解读工艺规程文档
- 查询工艺参数和表格
- 辅助编辑工艺文件

## 任务说明
根据用户查询，提供准确的工艺信息和专业建议。"""
    
    def _calculate_budget(self, max_tokens: int) -> Dict[str, int]:
        """计算 token 预算分配
        
        Args:
            max_tokens: 最大 token 数量
            
        Returns:
            各层的预算分配
        """
        # 按比例缩放
        scale = max_tokens / 8000
        
        budget = {}
        for key, value in self.DEFAULT_BUDGET.items():
            budget[key] = int(value * scale)
        
        return budget
    
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
