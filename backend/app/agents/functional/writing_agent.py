"""
撰写 Agent

负责工艺内容的编辑、表格填充、格式调整

集成 Search Agent 进行统一检索
支持用户反馈和多轮修改
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from app.agents.base_agent import BaseAgent
from app.agents.core import AgentRegistry
from app.agents.search import SearchAgent, SearchMode
from app.shared.logging import get_logger

logger = get_logger(__name__)


class FeedbackType(str, Enum):
    """用户反馈类型"""
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"


@dataclass
class UserFeedback:
    """用户反馈"""
    type: FeedbackType
    content: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class VersionHistory:
    """版本历史"""
    version: int
    content: str
    timestamp: float
    feedback: Optional[UserFeedback] = None


@AgentRegistry.register("writing")
class WritingAgent(BaseAgent):
    """
    撰写 Agent

    职责：
    - 工艺内容编辑
    - 表格填充
    - 格式调整
    - 多轮修改支持

    使用 Search Agent 进行统一检索
    """

    name = "writing"
    description = "负责工艺内容的编辑、表格填充、格式调整"
    tools = ["document_generator"]  # 移除 rag_retriever，使用 Search Agent

    # 支持的动作类型
    ACTION_TYPES = ["edit", "fill", "format", "generate"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化撰写 Agent

        Args:
            config: 配置参数
        """
        super().__init__(config)

        # 撰写相关配置
        self.default_format = self.config.get("default_format", "html")
        self.max_retrieval_results = self.config.get("max_retrieval_results", 5)

        # Search Agent 实例（依赖注入）
        self._search_agent: Optional[SearchAgent] = None

        # Dynamic writing preferences (loaded per session)
        self._writing_preferences: Optional["WritingPreferences"] = None

        # 版本历史（用于多轮修改）
        self._version_history: List[VersionHistory] = []
        self._current_version = 0

    @property
    def search_agent(self) -> SearchAgent:
        """获取或创建 Search Agent 实例"""
        if self._search_agent is None:
            self._search_agent = SearchAgent(self.config.get("search_agent", {}))
        return self._search_agent

    @search_agent.setter
    def search_agent(self, agent: SearchAgent):
        """设置 Search Agent 实例（依赖注入）"""
        self._search_agent = agent

    async def process(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理撰写任务

        Args:
            task: 任务描述
                - action: 动作类型 (edit/fill/format/generate)
                - target: 目标对象（表格/段落标识）
                - content: 编辑内容
                - requirements: 要求描述
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "result": Any,
                "document": Dict,
                "suggestions": List[str]
            }
        """
        try:
            action = task.get("action", "edit")

            if action not in self.ACTION_TYPES:
                return {
                    "success": False,
                    "error": f"不支持的动作类型: {action}",
                    "error_code": "INVALID_ACTION"
                }

            # 1. 使用 Search Agent 检索相关知识（如果有要求）
            knowledge = None
            if task.get("requirements"):
                knowledge = await self._search_knowledge(
                    task["requirements"],
                    task.get("search_mode", "comprehensive")
                )

            # 2. 根据动作类型执行
            if action == "edit":
                result = await self._do_edit(task, knowledge, context)
            elif action == "fill":
                result = await self._do_fill(task, knowledge, context)
            elif action == "format":
                result = await self._do_format(task, context)
            elif action == "generate":
                result = await self._do_generate(task, knowledge, context)
            else:
                result = {"success": False, "error": f"未知动作: {action}"}

            if not result.get("success"):
                return result

            # 3. 生成文档（如果需要）
            doc_result = None
            if task.get("generate_doc", True):
                doc_result = await self.use_tool(
                    "document_generator",
                    {
                        "content": result.get("content", ""),
                        "title": task.get("title", "工艺文件"),
                        "format": task.get("output_format", self.default_format)
                    }
                )

            logger.info(
                "writing_task_completed",
                action=action,
                target=task.get("target", ""),
                has_document=doc_result is not None
            )

            return {
                "success": True,
                "result": result,
                "document": doc_result,
                "suggestions": result.get("suggestions", [])
            }

        except Exception as e:
            logger.error("writing_task_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "WRITING_FAILED"
            }

    async def _do_edit(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行编辑操作

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            编辑结果
        """
        target = task.get("target", "")
        content = task.get("content", "")
        requirements = task.get("requirements", "")

        # 整合知识
        knowledge_context = ""
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            knowledge_context = "\n".join([
                r.get("content", "") for r in results[:3]
            ])

        # 这里应该调用 LLM 进行实际编辑
        # 目前返回模拟结果
        edited_content = f"[已编辑] {content}"

        if knowledge_context:
            edited_content += f"\n\n参考依据:\n{knowledge_context[:500]}"

        # 保存版本
        self._save_version(edited_content)

        return {
            "success": True,
            "content": edited_content,
            "target": target,
            "suggestions": ["建议检查术语一致性", "建议添加工艺参数"]
        }

    async def _do_fill(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行表格填充

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            填充结果
        """
        target = task.get("target", "")
        fields = task.get("fields", [])

        # 从知识中提取填充数据
        filled_data = {}
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            # 简单的字段提取
            for field in fields:
                for r in results:
                    content = r.get("content", "")
                    if field.lower() in content.lower():
                        filled_data[field] = f"[从知识库提取] {field}"
                        break

        return {
            "success": True,
            "content": f"表格 {target} 填充完成",
            "filled_data": filled_data,
            "unfilled_fields": [f for f in fields if f not in filled_data]
        }

    async def _do_format(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行格式调整

        Args:
            task: 任务描述
            context: 执行上下文

        Returns:
            格式调整结果
        """
        content = task.get("content", "")
        format_rules = task.get("format_rules", [])

        # 应用格式规则
        formatted_content = content

        return {
            "success": True,
            "content": formatted_content,
            "applied_rules": format_rules
        }

    async def _do_generate(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成新内容

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            生成结果
        """
        requirements = task.get("requirements", "")
        template = task.get("template", "standard")

        # 基于要求生成内容
        generated_content = f"根据要求生成的内容: {requirements}"

        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            if results:
                generated_content += f"\n\n参考:\n{results[0].get('content', '')[:300]}"

        # 保存版本
        self._save_version(generated_content)

        return {
            "success": True,
            "content": generated_content,
            "template": template
        }

    def load_preferences(self, preferences: "WritingPreferences") -> None:
        """
        Load dynamic writing preferences for this session.

        Args:
            preferences: WritingPreferences instance
        """
        from app.models.profile import WritingPreferences
        self._writing_preferences = preferences
        logger.info("writing_preferences_loaded", confidence=preferences.confidence)

    def _get_preference_prompt_fragment(self) -> str:
        """Generate a prompt fragment from loaded preferences."""
        if not self._writing_preferences:
            return ""

        prefs = self._writing_preferences
        lines = []

        if prefs.confidence > 0.3:
            lines.append(f"- 语气: {prefs.tone}")
            lines.append(f"- 详细程度: {prefs.detail_level}")
            lines.append(f"- 句式长度偏好: {prefs.preferred_sentence_length}")

            if not prefs.use_passive_voice:
                lines.append("- 尽量使用主动语态")
            if not prefs.include_examples:
                lines.append("- 不需要举例说明")
            if not prefs.include_caution_notes:
                lines.append("- 不需要额外注意事项")

            if prefs.avoid_phrases:
                lines.append(f"- 避免使用: {', '.join(prefs.avoid_phrases[:5])}")
            if prefs.custom_vocabulary:
                for cn, en in list(prefs.custom_vocabulary.items())[:5]:
                    lines.append(f"- 术语 {cn} 对应 {en}")

        if lines:
            return "\n## 用户写作偏好 (基于历史交互学习)\n" + "\n".join(lines)
        return ""

    async def _search_knowledge(
        self,
        query: str,
        mode: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        使用 Search Agent 检索知识

        Args:
            query: 查询字符串
            mode: 检索模式 (files_only/knowledge_only/comprehensive)

        Returns:
            检索结果
        """
        try:
            # 映射检索模式
            mode_mapping = {
                "files_only": SearchMode.FILES_ONLY,
                "knowledge_only": SearchMode.KNOWLEDGE_ONLY,
                "comprehensive": SearchMode.COMPREHENSIVE,
            }
            search_mode = mode_mapping.get(mode, SearchMode.COMPREHENSIVE)

            # 调用 Search Agent
            search_context = await self.search_agent.search(
                mode=search_mode,
                query=query,
                token_budget=4000  # 默认Token预算
            )

            # 转换为兼容格式
            results = []
            for ctx in search_context.contexts:
                results.append({
                    "content": ctx.content,
                    "source": ctx.source,
                    "score": ctx.relevance_score,
                    "metadata": ctx.metadata
                })

            logger.info(
                "search_agent_retrieval_completed",
                mode=mode,
                results_count=len(results),
                total_tokens=search_context.total_tokens,
                cache_hit=search_context.cache_hit
            )

            return {
                "success": True,
                "results": results,
                "total_tokens": search_context.total_tokens,
                "cache_hit": search_context.cache_hit
            }

        except Exception as e:
            logger.error("search_knowledge_failed", error=str(e), query=query[:100])
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    async def handle_feedback(
        self,
        feedback: UserFeedback,
        task: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理用户反馈（多轮修改支持）

        Args:
            feedback: 用户反馈
            task: 原始任务（可选）

        Returns:
            处理结果
        """
        if feedback.type == FeedbackType.ACCEPT:
            # 用户接受，标记完成
            logger.info("user_accepted", version=self._current_version)
            return {
                "success": True,
                "status": "accepted",
                "version": self._current_version,
                "message": "内容已确认"
            }

        elif feedback.type == FeedbackType.REJECT:
            # 用户拒绝，回滚或中止
            logger.info("user_rejected", version=self._current_version)
            return {
                "success": True,
                "status": "rejected",
                "version": self._current_version,
                "message": "内容已拒绝"
            }

        elif feedback.type == FeedbackType.MODIFY:
            # 用户要求修改
            if len(self._version_history) >= 3:
                return {
                    "success": False,
                    "status": "max_iterations_reached",
                    "message": "已达到最大修改次数（3次）"
                }

            # 基于反馈进行增量修改
            last_version = self._version_history[-1] if self._version_history else None
            if last_version is None:
                return {
                    "success": False,
                    "status": "no_content_to_modify",
                    "message": "没有可修改的内容"
                }

            # 执行增量修改
            modified_content = await self._incremental_modify(
                last_version.content,
                feedback
            )

            # 保存新版本
            self._current_version += 1
            new_version = VersionHistory(
                version=self._current_version,
                content=modified_content.get("content", ""),
                timestamp=__import__("time").time(),
                feedback=feedback
            )
            self._version_history.append(new_version)

            logger.info(
                "content_modified",
                version=self._current_version,
                feedback_type=feedback.type
            )

            return {
                "success": True,
                "status": "modified",
                "version": self._current_version,
                "content": modified_content.get("content"),
                "suggestions": modified_content.get("suggestions", [])
            }

        return {
            "success": False,
            "status": "unknown_feedback_type",
            "message": f"未知的反馈类型: {feedback.type}"
        }

    async def _incremental_modify(
        self,
        original_content: str,
        feedback: UserFeedback
    ) -> Dict[str, Any]:
        """
        增量修改内容

        Args:
            original_content: 原始内容
            feedback: 用户反馈

        Returns:
            修改后的内容
        """
        # 基于用户反馈内容进行修改
        suggestions = []

        # 如果有具体建议，检索相关知识
        if feedback.suggestions:
            additional_knowledge = await self._search_knowledge(
                " ".join(feedback.suggestions),
                mode="comprehensive"
            )

            if additional_knowledge.get("success"):
                for result in additional_knowledge.get("results", [])[:2]:
                    suggestions.append(f"参考: {result.get('content', '')[:200]}")

        # 模拟增量修改（实际应该调用LLM）
        modified_content = f"{original_content}\n\n[根据反馈修改]\n{feedback.content}"

        return {
            "content": modified_content,
            "suggestions": suggestions
        }

    def get_version_history(self) -> List[Dict[str, Any]]:
        """
        获取版本历史

        Returns:
            版本历史列表
        """
        return [
            {
                "version": v.version,
                "content": v.content[:500] + "..." if len(v.content) > 500 else v.content,
                "timestamp": v.timestamp,
                "feedback_type": v.feedback.type if v.feedback else None
            }
            for v in self._version_history
        ]

    def rollback(self, version: int) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            version: 目标版本号

        Returns:
            回滚结果
        """
        for v in self._version_history:
            if v.version == version:
                self._current_version = version
                logger.info("version_rollback", version=version)
                return {
                    "success": True,
                    "version": version,
                    "content": v.content
                }

        return {
            "success": False,
            "error": f"版本 {version} 不存在"
        }

    def _save_version(self, content: str, feedback: Optional[UserFeedback] = None):
        """
        保存版本到历史

        Args:
            content: 内容
            feedback: 关联的反馈
        """
        import time
        self._current_version += 1
        version = VersionHistory(
            version=self._current_version,
            content=content,
            timestamp=time.time(),
            feedback=feedback
        )
        self._version_history.append(version)
