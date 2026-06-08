"""
工艺文件辅助编辑系统 - 主控Agent (ProcessOrchestrator)
负责协调整个工艺文件编辑流程，管理子Agent调度和会话状态

集成任务记忆系统和上下文管理
使用新的三层架构：Orchestrator -> 功能Agent -> Tool

交互流程：
1. 意图识别 → 2. 信息完整性评估 → 3. 信息收集(如需) → 4. 预览生成 → 5. 用户确认 → 6. 任务执行

支持多轮迭代：
- 最大3轮迭代
- 用户反馈处理
- 增量修改
"""
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import time

import re as _re

from app.shared.logging import get_logger


def _strip_duplicate_heading(content: str, parent_title: str) -> str:
    """Remove a leading heading that duplicates the parent heading."""
    stripped = content.lstrip()
    # Match ## or ### heading (possibly with extra text after)
    m = _re.match(r"^#{1,3}\s+.*?\n+", stripped)
    if m:
        heading_text = stripped[:m.end()]
        # Check if the heading contains the parent title
        if parent_title in heading_text:
            return stripped[m.end():]
    return content
from .state_machine import ProcessStateMachine, ProcessState
from .dialog_manager import DialogManager
from .intent_recognizer import IntentRecognizer, IntentType
from .task_decomposer import TaskDecomposer

# 导入新的交互组件
from .info_assessor import InfoAssessor, AssessmentResult
from .interaction_manager import InteractionManager
from .interaction_models import (
    InteractionType,
    InputType,
    InfoRequestMessage,
    PreviewMessage,
    ConfirmationMessage,
    UserResponse,
)

# 导入新的Agent系统
from app.agents.core import AgentRegistry, WorkflowRegistry
from app.agents.functional import discover_agents

logger = get_logger(__name__)


class IterationResult(str, Enum):
    """迭代结果状态"""
    CONTINUE = "continue"
    COMPLETE = "complete"
    MAX_REACHED = "max_reached"
    ABORT = "abort"


@dataclass
class UserFeedback:
    """用户反馈"""
    type: str  # accept/modify/reject
    content: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class IterationHistory:
    """迭代历史记录"""
    iteration: int
    content: str
    feedback: Optional[UserFeedback] = None
    timestamp: float = field(default_factory=time.time)
    result: Optional[Dict[str, Any]] = None


class IterationManager:
    """
    迭代管理器

    管理多轮迭代循环：
    - 最大迭代次数：3
    - 用户反馈处理
    - 迭代历史记录
    """

    MAX_ITERATIONS = 3

    def __init__(self, max_iterations: int = 3):
        """
        初始化迭代管理器

        Args:
            max_iterations: 最大迭代次数
        """
        self.max_iterations = max_iterations
        self._current_iteration = 0
        self._history: List[IterationHistory] = []

    @property
    def current_iteration(self) -> int:
        """当前迭代次数"""
        return self._current_iteration

    @property
    def can_continue(self) -> bool:
        """是否可以继续迭代"""
        return self._current_iteration < self.max_iterations

    def process_feedback(self, feedback: UserFeedback) -> IterationResult:
        """
        处理用户反馈

        Args:
            feedback: 用户反馈

        Returns:
            迭代结果状态
        """
        if feedback.type == "accept":
            return IterationResult.COMPLETE
        elif feedback.type == "modify":
            if self.can_continue:
                return IterationResult.CONTINUE
            else:
                return IterationResult.MAX_REACHED
        else:  # reject
            return IterationResult.ABORT

    def start_iteration(self) -> int:
        """
        开始新一轮迭代

        Returns:
            新的迭代编号
        """
        self._current_iteration += 1
        return self._current_iteration

    def record_history(
        self,
        content: str,
        feedback: Optional[UserFeedback] = None,
        result: Optional[Dict[str, Any]] = None
    ):
        """
        记录迭代历史

        Args:
            content: 当前内容
            feedback: 用户反馈
            result: 执行结果
        """
        history = IterationHistory(
            iteration=self._current_iteration,
            content=content,
            feedback=feedback,
            result=result
        )
        self._history.append(history)

    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取迭代历史

        Returns:
            迭代历史列表
        """
        return [
            {
                "iteration": h.iteration,
                "content": h.content[:500] + "..." if len(h.content) > 500 else h.content,
                "feedback_type": h.feedback.type if h.feedback else None,
                "timestamp": h.timestamp
            }
            for h in self._history
        ]

    def reset(self):
        """重置迭代状态"""
        self._current_iteration = 0
        self._history.clear()


class ProcessOrchestrator:
    """
    工艺文件主控Agent

    职责：
    1. 接收用户输入的工艺意图
    2. 识别意图并分解为子任务
    3. 调度相应的子Agent执行任务
    4. 管理会话状态和上下文
    5. 聚合结果并返回给用户
    6. 持久化任务记忆

    使用方式：
    ```python
    # 简单模式（向后兼容）
    orchestrator = ProcessOrchestrator()

    # 完整模式（推荐）
    from app.repositories import get_repository
    from app.services.context_builder import ContextBuilder

    repo = get_repository()
    orchestrator = ProcessOrchestrator(
        repository=repo,
        context_builder=ContextBuilder(repo),
    )

    # 处理任务
    result = await orchestrator.process_intent(
        user_input="帮我修改电缆装配表",
        task_name="电缆装配编辑",
        source_docs=["全单电缆装配规程.pdf"],
    )
    ```
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        repository=None,
        context_builder=None,
    ):
        """
        初始化主控Agent

        Args:
            config: 配置参数
            repository: TaskMemoryRepository实例（可选）
            context_builder: ContextBuilder实例（可选）
        """
        self.config = config or {}
        self.repository = repository
        self.context_builder = context_builder

        # 初始化核心组件
        self.state_machine = ProcessStateMachine(
            repository=repository,
            task_id=None,  # 后续设置
        )
        self.dialog_manager = DialogManager(
            repository=repository,
            task_id=None,  # 后续设置
        )
        self.intent_recognizer = IntentRecognizer()
        self.task_decomposer = TaskDecomposer()

        # 初始化新的交互组件
        self.info_assessor = InfoAssessor(config)
        self.interaction_manager = InteractionManager(
            repository=repository,
            dialog_manager=self.dialog_manager
        )

        # 初始化功能Agent系统
        discover_agents()  # 触发Agent自动发现
        self._agents: Dict[str, Any] = {}
        self._init_agents()

        # 工作流配置
        self.workflows = {
            "full_edit": ["writing", "proofread", "review"],
            "quick_edit": ["writing", "proofread"],
            "review_only": ["review"],
            "proofread_only": ["proofread"],
        }

        # 当前任务ID
        self.current_task_id: Optional[str] = None

        # 当前收集的信息缓存
        self._collected_info: Dict[str, Any] = {}

        # 迭代管理器
        self._iteration_manager = IterationManager(
            max_iterations=self.config.get("max_iterations", 3)
        )

        logger.info(
            "process_orchestrator_initialized",
            config_keys=list(self.config.keys()),
            has_repository=repository is not None,
            has_context_builder=context_builder is not None,
            available_agents=list(self._agents.keys()),
            max_iterations=self._iteration_manager.max_iterations
        )

    def _init_agents(self):
        """
        初始化功能Agent

        从AgentRegistry获取已注册的Agent实例
        """
        agent_names = ["writing", "proofread", "review"]

        for name in agent_names:
            agent = AgentRegistry.create(name, self.config.get(name))
            if agent is not None:
                self._agents[name] = agent
                logger.debug("agent_initialized", agent=name)
            else:
                logger.warning("agent_not_available", agent=name)

        # Load dynamic preferences into WritingAgent
        self._load_writing_preferences()

    def _load_writing_preferences(self) -> None:
        """Load dynamic writing preferences from domain profile into the writing agent."""
        if "writing" not in self._agents:
            return

        try:
            from app.models.profile import WritingPreferences, Profile
            from app.config import settings
            from pathlib import Path

            domain = self.config.get("domain", "assembly")
            profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"

            if profile_path.exists():
                profile = Profile.from_json(profile_path)
                prefs = WritingPreferences.from_profile(profile)
            else:
                prefs = WritingPreferences()

            writing_agent = self._agents["writing"]
            if hasattr(writing_agent, "load_preferences"):
                writing_agent.load_preferences(prefs)
        except Exception as e:
            logger.debug("preferences_load_skipped", error=str(e))

    async def create_task(
        self,
        task_name: str,
        task_type: str = "craft_document_edit",
        source_docs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        创建新任务

        Args:
            task_name: 任务名称
            task_type: 任务类型
            source_docs: 关联的源文档
            tags: 标签

        Returns:
            任务ID
        """
        if not self.repository:
            # 内存模式：生成简单ID
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            task_id = f"{task_name}_{timestamp}"
            self.current_task_id = task_id
            logger.info("task_created_memory_mode", task_id=task_id)
            return task_id

        # Repository模式：持久化创建
        task_id = self.repository.create_task(
            task_name=task_name,
            task_type=task_type,
            source_docs=source_docs,
            tags=tags,
        )

        # 设置当前任务
        self.current_task_id = task_id
        self.state_machine.set_task(task_id)
        self.dialog_manager.set_task(task_id)

        logger.info(
            "task_created",
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            source_docs=source_docs,
        )

        return task_id

    async def load_task(self, task_id: str) -> bool:
        """
        加载已有任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功加载
        """
        if not self.repository:
            logger.warning("load_task_requires_repository")
            return False

        if not self.repository.task_exists(task_id):
            logger.warning("task_not_found", task_id=task_id)
            return False

        self.current_task_id = task_id
        self.state_machine.set_task(task_id)
        self.dialog_manager.set_task(task_id)

        logger.info("task_loaded", task_id=task_id)
        return True

    async def process_intent(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        task_name: Optional[str] = None,
        source_docs: Optional[List[str]] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理用户输入的工艺意图

        Args:
            user_input: 用户输入的工艺描述
            context: 会话上下文
            task_name: 任务名称（新任务时使用）
            source_docs: 源文档列表（新任务时使用）
            task_id: 已有任务ID（继续任务时使用）

        Returns:
            处理结果，包含建议、问题或生成的工艺文件
        """
        try:
            # 1. 确定任务ID
            if task_id:
                # 继续已有任务
                if not await self.load_task(task_id):
                    return {
                        "success": False,
                        "error": f"任务不存在: {task_id}",
                    }
            elif not self.current_task_id:
                # 创建新任务
                name = task_name or "工艺编辑任务"
                await self.create_task(
                    task_name=name,
                    source_docs=source_docs,
                )

            # 2. Auto-recover from ERROR state on new request
            if self.state_machine.current_state == ProcessState.ERROR:
                logger.info("auto_recovering_from_error", task_id=self.current_task_id)
                await self.state_machine.transition_to(
                    ProcessState.IDLE,
                    trigger="auto_recovery",
                )

            # 3. 构建上下文
            full_context = await self._build_context(context)

            # 4. 更新会话状态
            await self.state_machine.transition_to(
                ProcessState.INTENT_RECOGNITION,
                context_update={"user_input": user_input},
                trigger="process_intent",
            )

            # 4. 识别意图
            intent = await self.intent_recognizer.recognize(user_input, full_context)
            logger.info("intent_recognized", intent_type=intent.get("type"), confidence=intent.get("confidence"))

            # 4.1 generation_mode shortcut: skip intent recognition, go directly to draft_complete
            gen_mode = (context or {}).get("generation_mode") or (full_context or {}).get("generation_mode")
            if gen_mode in ("generate", "fill"):
                logger.info("generation_mode_shortcut", mode=gen_mode)
                if self.repository and self.current_task_id:
                    self.repository.add_message(
                        task_id=self.current_task_id,
                        role="user",
                        content=user_input,
                        metadata={"intent": {"type": "draft_complete", "generation_mode": gen_mode}},
                    )
                merged_context = {**(context or {}), **full_context, "generation_mode": gen_mode}
                # generate: treat as all chapters missing; fill: detect gaps
                if gen_mode == "generate":
                    merged_context["force_all_chapters"] = True
                return await self._handle_draft_complete(user_input, intent, merged_context)

            # 4.5 Route DRAFT_COMPLETE to dedicated handler
            # This includes temp uploaded file scenarios (no draft_id)
            if intent.get("type") == "draft_complete":
                # Record user message before routing
                if self.repository and self.current_task_id:
                    self.repository.add_message(
                        task_id=self.current_task_id,
                        role="user",
                        content=user_input,
                        metadata={"intent": intent},
                    )
                # Merge context + uploaded file info
                merged_context = {**(context or {}), **full_context}
                return await self._handle_draft_complete(user_input, intent, merged_context)

            # 5. 分解任务
            tasks = await self.task_decomposer.decompose(intent)
            logger.info("tasks_decomposed", task_count=len(tasks), task_types=[t.get("type") for t in tasks])

            # 6. 记录用户消息
            if self.repository and self.current_task_id:
                self.repository.add_message(
                    task_id=self.current_task_id,
                    role="user",
                    content=user_input,
                    metadata={"intent": intent},
                )

            # 7. 执行任务（根据状态机）
            results = []
            for task in tasks:
                # 根据任务类型调度相应的子Agent
                agent_result = await self._dispatch_to_sub_agent(task)
                results.append(agent_result)

                # 更新状态机
                await self.state_machine.transition_to(
                    ProcessState.TASK_EXECUTION,
                    context_update={"last_task": task.get("type")},
                    trigger=task.get("type"),
                )

            # 8. 聚合结果
            aggregated_result = await self._aggregate_results(results)

            # 9. 更新到完成状态
            await self.state_machine.transition_to(
                ProcessState.COMPLETION,
                trigger="all_tasks_completed",
            )

            # 10. 记录助手回复
            if self.repository and self.current_task_id:
                response_content = aggregated_result.get("generated_content", "") or \
                                  aggregated_result.get("message", "处理完成")
                self.repository.add_message(
                    task_id=self.current_task_id,
                    role="assistant",
                    content=response_content,
                    metadata={
                        "tasks_executed": [t.get("type") for t in tasks],
                        "state": "completed",
                    },
                )

            # 11. 保存对话历史
            await self.dialog_manager.add_interaction(
                user_input=user_input,
                intent=intent,
                tasks=tasks,
                result=aggregated_result,
            )

            return {
                "success": True,
                "task_id": self.current_task_id,
                "intent": intent,
                "tasks": tasks,
                "result": aggregated_result,
                "state": self.state_machine.current_state.value,
            }

        except Exception as e:
            logger.error("process_intent_failed", error=str(e), user_input=user_input)
            await self.state_machine.transition_to(ProcessState.ERROR, trigger="exception")

            return {
                "success": False,
                "task_id": self.current_task_id,
                "error": str(e),
                "state": self.state_machine.current_state.value,
            }

    async def _build_context(self, additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        构建完整上下文

        Args:
            additional_context: 额外的上下文信息

        Returns:
            合并后的上下文
        """
        context = {
            "task_id": self.current_task_id,
            "state": self.state_machine.get_current_state().value,
            "dialog_context": await self.dialog_manager.get_context(),
        }

        # 如果有ContextBuilder，构建完整上下文
        if self.context_builder and self.current_task_id and self.repository:
            # 从Repository获取任务元信息
            meta = self.repository.get_meta(self.current_task_id)
            if meta:
                context["task_meta"] = {
                    "task_name": meta.task_name,
                    "task_type": meta.task_type,
                    "source_documents": meta.source_documents,
                    "tags": meta.tags,
                }

                # 加载源文档内容
                if meta.source_documents:
                    doc_context = self.context_builder.context_manager.build_document_context(
                        meta.source_documents,
                        include_html=False,
                        max_tables=30,
                    )
                    context["document_context"] = doc_context

        # 合并额外上下文
        if additional_context:
            context.update(additional_context)

        return context

    async def _dispatch_to_sub_agent(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        调度任务到相应的功能Agent

        Args:
            task: 任务描述

        Returns:
            Agent执行结果
        """
        task_type = task.get("type")

        # 新的任务类型映射到功能Agent
        agent_mapping = {
            "writing": "writing",
            "edit": "writing",
            "fill": "writing",
            "format": "writing",
            "generate": "writing",
            "proofread": "proofread",
            "terminology_alignment": "proofread",
            "data_validation": "proofread",
            "review": "review",
            "compliance_check": "review",
            "rationality_check": "review",
            "risk_assessment": "review",
        }

        # 获取对应的Agent名称
        agent_name = agent_mapping.get(task_type)

        if agent_name and agent_name in self._agents:
            agent = self._agents[agent_name]

            try:
                # 构建任务参数
                agent_task = {
                    "action": task.get("action") or task_type,
                    "content": task.get("content", ""),
                    "target": task.get("target"),
                    "requirements": task.get("requirements"),
                    **task.get("params", {})
                }

                # Pass template fields for structured JSON output
                for key in ("template_slots", "chapter_code", "chapter_type",
                            "chapter_title", "ai_guidance"):
                    if key in task:
                        agent_task[key] = task[key]

                # Load domain profile for review-related tasks
                if agent_name in ("review", "proofread"):
                    domain = task.get("domain", "assembly")
                    try:
                        from app.models.profile import Profile
                        from app.config import settings
                        from pathlib import Path
                        profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"
                        if profile_path.exists():
                            agent_task["profile"] = Profile.from_json(profile_path).to_dict()
                    except Exception as e:
                        logger.warning(f"profile_load_failed for domain={domain}: {e}")

                # 调用Agent处理
                result = await agent.process(agent_task)

                logger.info(
                    "agent_dispatch_completed",
                    agent=agent_name,
                    task_type=task_type,
                    success=result.get("success", False)
                )

                return {
                    "type": task_type,
                    "agent": agent_name,
                    "status": "completed" if result.get("success") else "failed",
                    "result": result
                }

            except Exception as e:
                logger.error(
                    "agent_dispatch_failed",
                    agent=agent_name,
                    task_type=task_type,
                    error=str(e)
                )
                return {
                    "type": task_type,
                    "agent": agent_name,
                    "status": "error",
                    "error": str(e)
                }

        # 兼容旧的任务类型
        legacy_mapping = {
            "pdf_parsing": {"status": "pending", "message": "PDF解析已移至后台服务"},
            "rag_retrieval": {"status": "pending", "message": "RAG检索通过Tool调用"},
        }

        if task_type in legacy_mapping:
            return {"type": task_type, **legacy_mapping[task_type]}

        return {"type": task_type, "status": "unknown", "message": f"未知任务类型: {task_type}"}

    async def _select_workflow(self, intent: Dict[str, Any]) -> List[str]:
        """
        根据意图选择工作流

        Args:
            intent: 意图识别结果

        Returns:
            Agent执行序列
        """
        intent_type = intent.get("type", "")
        complexity = intent.get("complexity", "simple")

        # 根据意图类型选择工作流
        if intent_type in ["full_edit", "complete_rewrite"]:
            return self.workflows["full_edit"]
        elif intent_type in ["quick_edit", "minor_change"]:
            return self.workflows["quick_edit"]
        elif intent_type in ["review", "compliance_only"]:
            return self.workflows["review_only"]
        elif intent_type in ["proofread", "terminology_check"]:
            return self.workflows["proofread_only"]
        else:
            # 默认根据复杂度选择
            if complexity == "complex":
                return self.workflows["full_edit"]
            else:
                return self.workflows["quick_edit"]

    async def execute_workflow(
        self,
        workflow_name: str,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute specified workflow with rollback on failure.

        If any agent in the pipeline fails, the workflow stops and returns
        the last successful content + failure details. Content is NOT
        silently overwritten on failure.

        Args:
            workflow_name: workflow name
            task: task description
            context: execution context

        Returns:
            workflow execution result
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return {
                "success": False,
                "error": f"工作流不存在: {workflow_name}"
            }

        results = []
        current_content = task.get("content", "")
        # Snapshot original content for rollback
        original_content = current_content

        for agent_name in workflow:
            if agent_name not in self._agents:
                logger.warning("agent_not_in_workflow", agent=agent_name)
                continue

            agent = self._agents[agent_name]

            # Build agent task
            agent_task = {
                "content": current_content,
                **task
            }

            # Load domain profile for review-related agents
            if agent_name in ("review", "proofread"):
                domain = task.get("domain", "assembly")
                try:
                    from app.models.profile import Profile
                    from app.config import settings
                    from pathlib import Path
                    profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"
                    if profile_path.exists():
                        agent_task["profile"] = Profile.from_json(profile_path).to_dict()
                except Exception as e:
                    logger.warning(f"profile_load_failed for domain={domain}: {e}")

            # Execute agent
            try:
                result = await agent.process(agent_task, context)
            except Exception as e:
                # Agent crashed: stop pipeline, keep last good content
                logger.error(
                    "workflow_agent_crashed",
                    agent=agent_name,
                    error=str(e),
                )
                return {
                    "success": False,
                    "workflow": workflow_name,
                    "failed_at": agent_name,
                    "error": str(e),
                    "final_content": current_content,
                    "results": results,
                    "rollback": current_content != original_content,
                }

            results.append({
                "agent": agent_name,
                "result": result
            })

            # Update content only on success
            if result.get("success") and result.get("result", {}).get("content"):
                current_content = result["result"]["content"]

            # Review failure: stop pipeline, do not pass bad content forward
            if agent_name == "review" and not result.get("result", {}).get("passed"):
                logger.warning(
                    "workflow_review_failed",
                    issues=result.get("result", {}).get("warnings", [])
                )
                return {
                    "success": False,
                    "workflow": workflow_name,
                    "failed_at": "review",
                    "review_issues": result.get("result", {}).get("warnings", []),
                    "final_content": current_content,
                    "results": results,
                }

        return {
            "success": True,
            "workflow": workflow_name,
            "results": results,
            "final_content": current_content
        }

    async def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        聚合子Agent的执行结果

        Args:
            results: 子Agent结果列表

        Returns:
            聚合后的结果
        """
        # 简单的结果聚合逻辑
        aggregated = {
            "components": [],
            "suggestions": [],
            "warnings": [],
            "generated_content": None
        }

        for result in results:
            if result.get("status") == "completed":
                aggregated["components"].append(result)

                # 收集建议和警告
                if "suggestions" in result:
                    aggregated["suggestions"].extend(result["suggestions"])
                if "warnings" in result:
                    aggregated["warnings"].extend(result["warnings"])

                # 如果有生成内容，合并
                if "generated_content" in result:
                    if aggregated["generated_content"] is None:
                        aggregated["generated_content"] = result["generated_content"]
                    else:
                        # 简单的合并逻辑
                        aggregated["generated_content"] += "\n\n" + result["generated_content"]

        return aggregated

    async def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取对话历史

        Args:
            limit: 返回的历史记录数量

        Returns:
            对话历史列表
        """
        return await self.dialog_manager.get_history(limit)

    async def get_task_context(self) -> str:
        """
        获取当前任务的完整上下文（用于LLM）

        Returns:
            格式化的上下文字符串
        """
        if not self.current_task_id:
            return "# 无当前任务"

        if self.context_builder:
            return self.context_builder.build_context(self.current_task_id)

        # 简单上下文
        return f"# 当前任务\n任务ID: {self.current_task_id}\n状态: {self.state_machine.current_state.value}"

    async def reset_conversation(self):
        """
        重置对话状态
        """
        await self.state_machine.reset()
        await self.dialog_manager.clear()
        self.current_task_id = None
        logger.info("conversation_reset")

    async def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        列出任务

        Args:
            status: 按状态过滤
            limit: 返回数量限制

        Returns:
            任务列表
        """
        if not self.repository:
            return []

        from app.models.task_memory import TaskStatus
        status_enum = TaskStatus(status) if status else None

        tasks = self.repository.list_tasks(status=status_enum, limit=limit)

        return [
            {
                "task_id": t.task_id,
                "task_name": t.task_name,
                "task_type": t.task_type,
                "status": t.status.value,
                "created_at": t.created_at.isoformat(),
                "source_documents": t.source_documents,
            }
            for t in tasks
        ]

    async def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务详细信息

        Args:
            task_id: 任务ID

        Returns:
            任务信息
        """
        if not self.repository:
            return None

        meta = self.repository.get_meta(task_id)
        if not meta:
            return None

        state = self.repository.get_state(task_id)

        return {
            "task_id": meta.task_id,
            "task_name": meta.task_name,
            "task_type": meta.task_type,
            "status": meta.status.value,
            "created_at": meta.created_at.isoformat(),
            "updated_at": meta.updated_at.isoformat(),
            "source_documents": meta.source_documents,
            "tags": meta.tags,
            "current_state": state.current_state.value if state else None,
        }

    # ============== 新的交互式流程 ==============

    async def process_intent_with_interaction(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        task_name: Optional[str] = None,
        source_docs: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        user_response: Optional[UserResponse] = None,
    ) -> Dict[str, Any]:
        """
        处理用户意图（带交互确认）

        新流程：
        1. 意图识别
        2. 信息完整性评估
        3. 如缺信息 → 返回请求，等待用户补充
        4. 生成预览
        5. 等待用户确认
        6. 执行任务

        Args:
            user_input: 用户输入
            context: 上下文
            task_name: 任务名称
            source_docs: 源文档
            task_id: 任务ID
            user_response: 用户响应（补充信息时使用）

        Returns:
            处理结果或交互请求
        """
        try:
            # 0. 处理用户响应（如果有）
            if user_response:
                return await self._handle_user_response(user_response)

            # 1. 确定任务ID
            if task_id:
                if not await self.load_task(task_id):
                    return {"success": False, "error": f"任务不存在: {task_id}"}
            elif not self.current_task_id:
                name = task_name or "工艺编辑任务"
                await self.create_task(task_name=name, source_docs=source_docs)

            # 2. 构建上下文
            full_context = await self._build_context(context)
            full_context["user_input"] = user_input

            # 3. 状态转换到意图识别
            await self.state_machine.transition_to(
                ProcessState.INTENT_RECOGNITION,
                context_update={"user_input": user_input},
                trigger="process_intent",
            )

            # 4. 识别意图
            intent = await self.intent_recognizer.recognize(user_input, full_context)
            logger.info("intent_recognized", intent_type=intent.get("type"))

            # 4.5 draft_complete 快速路径：跳过信息评估，直接进入初稿分析
            if intent.get("type") == IntentType.DRAFT_COMPLETE.value:
                return await self._handle_draft_complete(
                    user_input=user_input,
                    intent=intent,
                    context=full_context,
                )

            # 5. 状态转换到信息评估
            await self.state_machine.transition_to(
                ProcessState.INFO_ASSESSMENT,
                trigger="intent_recognized"
            )

            # 6. 评估信息完整性
            assessment = await self.info_assessor.assess(intent, full_context)

            # 7. 如果信息不完整，请求用户补充
            if not assessment.is_complete:
                await self.state_machine.transition_to(
                    ProcessState.INFO_COLLECTION,
                    trigger="info_incomplete"
                )

                # 生成信息请求消息
                missing_info = self.info_assessor.get_missing_info_message(assessment)
                info_request = await self.interaction_manager.request_missing_info(
                    missing_info={
                        "high_priority": [
                            {
                                "name": m.item.name,
                                "description": m.item.description,
                                "example": m.item.example,
                                "impact": m.item.impact,
                                "input_type": m.item.input_type.value
                            }
                            for m in assessment.missing_high_priority
                        ],
                        "medium_priority": [
                            {
                                "name": m.item.name,
                                "description": m.item.description,
                                "example": m.item.example,
                                "impact": m.item.impact,
                                "input_type": m.item.input_type.value
                            }
                            for m in assessment.missing_medium_priority
                        ],
                        "can_skip": assessment.can_proceed_with_defaults
                    },
                    context=full_context
                )

                # 暂停等待用户输入
                await self.state_machine.transition_to(
                    ProcessState.PAUSED,
                    trigger="awaiting_user_input"
                )

                # 缓存当前状态
                self._collected_info["intent"] = intent
                self._collected_info["context"] = full_context
                self._collected_info["assessment"] = assessment

                return {
                    "success": True,
                    "requires_response": True,
                    "interaction_type": InteractionType.INFO_REQUEST.value,
                    "message": info_request.message,
                    "missing_items": [item.dict() for item in info_request.missing_items],
                    "suggestions": info_request.suggestions,
                    "state": self.state_machine.current_state.value,
                }

            # 8. 信息完整，生成预览
            await self.state_machine.transition_to(
                ProcessState.PREVIEW_GENERATION,
                trigger="info_complete"
            )

            # 合并收集的信息
            collected_info = {**assessment.available_info, **self._collected_info}

            preview = await self.interaction_manager.generate_preview(
                intent=intent,
                collected_info=collected_info,
                context=full_context
            )

            # 9. 等待用户确认
            await self.state_machine.transition_to(
                ProcessState.USER_CONFIRMATION,
                trigger="preview_generated"
            )

            # 生成确认消息
            confirmation = await self.interaction_manager.generate_confirmation(
                message=f"任务预览：\n\n📌 方向：{preview.direction}\n📊 结果：{preview.expected_result}\n\n确认开始执行？",
                options=[
                    {"label": "确认执行", "value": "confirm"},
                    {"label": "需要修改", "value": "modify"},
                    {"label": "取消", "value": "cancel"}
                ]
            )

            # 暂停等待确认
            await self.state_machine.transition_to(
                ProcessState.PAUSED,
                trigger="awaiting_confirmation"
            )

            # 缓存当前状态
            self._collected_info["intent"] = intent
            self._collected_info["context"] = full_context
            self._collected_info["collected_info"] = collected_info

            return {
                "success": True,
                "requires_response": True,
                "interaction_type": InteractionType.PREVIEW.value,
                "direction": preview.direction,
                "expected_result": preview.expected_result,
                "confirm_options": confirmation.options,
                "state": self.state_machine.current_state.value,
            }

        except Exception as e:
            logger.error("process_intent_with_interaction_failed", error=str(e))
            await self.state_machine.transition_to(ProcessState.ERROR, trigger="exception")
            return {
                "success": False,
                "error": str(e),
                "state": self.state_machine.current_state.value,
            }

    async def _handle_draft_plan_response(self, response: UserResponse) -> Dict[str, Any]:
        """处理 draft_complete 方案的确认响应

        Args:
            response: 用户响应

        Returns:
            执行结果或取消确认
        """
        user_choice = ""
        if hasattr(response, "data") and isinstance(response.data, dict):
            user_choice = response.data.get("choice", "")
        elif hasattr(response, "content"):
            content = (response.content or "").lower()
            if "确认" in content or "confirm" in content:
                user_choice = "confirm"
            elif "取消" in content or "cancel" in content:
                user_choice = "cancel"
            else:
                user_choice = "modify"

        if user_choice == "confirm":
            # 确认执行
            return await self._execute_draft_modification()

        elif user_choice == "cancel":
            # 取消
            await self.state_machine.transition_to(ProcessState.IDLE, trigger="user_cancel")
            self._collected_info.clear()
            return {
                "success": True,
                "message": "已取消初稿修改",
                "state": self.state_machine.current_state.value,
            }

        else:
            # 需要调整：返回让用户提供更具体的指示
            return {
                "success": True,
                "requires_response": True,
                "interaction_type": "draft_plan_review",
                "message": "请说明需要调整的内容：",
                "state": self.state_machine.current_state.value,
            }

    async def _handle_user_response(self, response: UserResponse) -> Dict[str, Any]:
        """处理用户响应"""
        # 检查是否是 draft_complete 确认流程
        if self._collected_info.get("modification_plan") and (
            self._collected_info.get("draft_id") or self._collected_info.get("is_temp_upload")
        ):
            return await self._handle_draft_plan_response(response)

        # 处理响应
        result = await self.interaction_manager.process_user_response(response)

        if not result.get("success"):
            return result

        action = result.get("action")

        # 根据action继续流程
        if action == "continue_assessment":
            # 用户补充了信息，重新评估
            new_info = result.get("collected_info", {})
            self._collected_info.update(new_info)

            # 合并到上下文
            context = self._collected_info.get("context", {})
            context["collected_info"] = self._collected_info

            # 重新评估
            intent = self._collected_info.get("intent", {})
            assessment = await self.info_assessor.assess(intent, context)

            if not assessment.is_complete:
                # 仍需更多信息
                missing_info = self.info_assessor.get_missing_info_message(assessment)
                info_request = await self.interaction_manager.request_missing_info(
                    missing_info={
                        "high_priority": [
                            {
                                "name": m.item.name,
                                "description": m.item.description,
                                "example": m.item.example,
                                "impact": m.item.impact,
                                "input_type": m.item.input_type.value
                            }
                            for m in assessment.missing_high_priority
                        ],
                        "medium_priority": [
                            {
                                "name": m.item.name,
                                "description": m.item.description,
                                "example": m.item.example,
                                "impact": m.item.impact,
                                "input_type": m.item.input_type.value
                            }
                            for m in assessment.missing_medium_priority
                        ],
                        "can_skip": assessment.can_proceed_with_defaults
                    },
                    context=context
                )
                return {
                    "success": True,
                    "requires_response": True,
                    "interaction_type": InteractionType.INFO_REQUEST.value,
                    "message": info_request.message,
                    "missing_items": [item.dict() for item in info_request.missing_items],
                    "suggestions": info_request.suggestions,
                }

            # 信息完整，生成预览
            preview = await self.interaction_manager.generate_preview(
                intent=intent,
                collected_info=self._collected_info,
                context=context
            )

            confirmation = await self.interaction_manager.generate_confirmation(
                message=f"任务预览：\n\n📌 方向：{preview.direction}\n📊 结果：{preview.expected_result}\n\n确认开始执行？",
                options=[
                    {"label": "确认执行", "value": "confirm"},
                    {"label": "需要修改", "value": "modify"},
                    {"label": "取消", "value": "cancel"}
                ]
            )

            return {
                "success": True,
                "requires_response": True,
                "interaction_type": InteractionType.PREVIEW.value,
                "direction": preview.direction,
                "expected_result": preview.expected_result,
                "confirm_options": confirmation.options,
            }

        elif action == "start_execution":
            # 用户确认，开始执行
            return await self._execute_confirmed_task()

        elif action == "cancel":
            # 用户取消
            await self.state_machine.transition_to(ProcessState.IDLE, trigger="user_cancel")
            return {
                "success": True,
                "message": "任务已取消",
                "state": self.state_machine.current_state.value,
            }

        return result

    # ============== Draft Complete 工作流 ==============

    async def _handle_draft_complete(
        self,
        user_input: str,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 draft_complete 意图

        流程（基于章节索引）：
        1. 加载画像
        2. 加载章节索引 + 读取初稿
        3. 结构对比：章节索引 vs 初稿 → 缺失章节列表
        4. 按缺失章节提取原文（get_chapter_content）
        5. 生成修改方案 + 返回让用户确认

        Args:
            user_input: 用户输入
            intent: 意图识别结果
            context: 会话上下文

        Returns:
            修改方案或交互请求
        """
        try:
            # 1. 状态转换到 DRAFT_ANALYSIS
            await self.state_machine.transition_to(
                ProcessState.DRAFT_ANALYSIS,
                context_update={"intent": intent, "user_input": user_input},
                trigger="draft_complete_detected",
            )

            # 2. 加载画像
            profile_context = await self._load_profile_context(context)

            # 3. 加载章节索引
            from app.services.hierarchical_context import hierarchical_context
            chapter_indexes = hierarchical_context.get_all_chapter_indexes()

            # Build a compact chapter summary for the LLM
            chapter_summary_lines = []
            for idx in chapter_indexes:
                for ch in idx.get("chapters", []):
                    pages = ch["pages"]
                    page_range = f"第{pages[0]}-{pages[-1]}页" if len(pages) > 1 else f"第{pages[0]}页"
                    chapter_summary_lines.append(
                        f"- {ch['title']} ({page_range}, {ch['page_count']}页)"
                    )
            chapter_summary = "\n".join(chapter_summary_lines) if chapter_summary_lines else "（无章节索引）"
            doc_name = chapter_indexes[0]["doc_name"] if chapter_indexes else ""

            # 4. 构建素材状态
            material_status = hierarchical_context.get_material_status(user_input)
            material_instruction = self._build_material_status_instruction(material_status)

            # 5. 读取初稿内容
            # For generate mode (force_all), draft_content is optional since
            # all chapters will be treated as missing regardless.
            force_all = context.get("force_all_chapters", False)
            draft_content, draft_id = await self._load_draft_content(context)
            if draft_content is None:
                draft_content = context.get("uploaded_file_content", "")
                if draft_content:
                    draft_id = context.get("draft_id")
                    logger.info("draft_loaded_from_temp_upload", content_length=len(draft_content))
                elif not force_all:
                    # fill mode without draft: fall back to generate (treat all as missing)
                    gen_mode = context.get("generation_mode")
                    if gen_mode == "fill":
                        logger.info("fill_mode_no_draft_fallback_to_generate")
                        force_all = True
                    else:
                        return {
                            "success": False,
                            "error": "未找到初稿，请先上传工艺文件初稿，或在上下文中提供 draft_id",
                            "state": self.state_machine.current_state.value,
                        }

            # 6. 结构对比 Agent：章节索引 vs 初稿 → 缺失章节
            # (force_all already determined above, may be overridden for fill-no-draft fallback)
            if force_all:
                # generate mode: treat ALL indexed chapters as missing
                missing_chapters = []
                for idx in chapter_indexes:
                    for ch in idx.get("chapters", []):
                        missing_chapters.append({
                            "title": ch["title"],
                            "pages": ch["pages"],
                            "page_count": ch["page_count"],
                            "_doc_dir": idx.get("_doc_dir", ""),
                            "reason": "full generation",
                        })
                logger.info("force_all_chapters", count=len(missing_chapters))
            else:
                missing_chapters = await self._detect_missing_chapters(
                    chapter_summary=chapter_summary,
                    draft_content=draft_content,
                    user_requirement=user_input,
                )

            logger.info(
                "chapter_diff_complete",
                total_chapters=len(chapter_summary_lines),
                missing_count=len(missing_chapters),
                missing_titles=[mc.get("title", "") for mc in missing_chapters],
                chapter_indexes_count=len(chapter_indexes),
            )

            # 7. 按缺失章节提取原文（大章节按子章节拆分）
            chapter_source_texts: Dict[str, str] = {}
            chapter_sub_sources: Dict[str, Dict[str, str]] = {}
            # Unified: all chapter titles that have source text (for ordering)
            available_titles: List[str] = []

            # Track chapters without source text for context-based generation
            no_source_titles: List[str] = []

            for mc in missing_chapters:
                title = mc.get("title", "")
                doc_dir = mc.get("_doc_dir", "")
                pages = mc.get("pages", [])
                page_count = mc.get("page_count", 0)
                sub_chapters = mc.get("sub_chapters", [])

                # Chapters without doc_dir: generate from overall context
                if not doc_dir:
                    no_source_titles.append(title)
                    chapter_source_texts[title] = ""
                    available_titles.append(title)
                    continue

                if page_count > 5 and sub_chapters:
                    sub_sources: Dict[str, str] = {}
                    for sc in sub_chapters:
                        sc_pages = sc.get("pages", [])
                        if not sc_pages:
                            continue
                        sc_text = hierarchical_context.get_pages_content(
                            doc_dir_name=doc_dir,
                            start_page=sc_pages[0],
                            end_page=sc_pages[-1],
                        )
                        if sc_text:
                            sub_sources[sc["title"]] = sc_text
                    if sub_sources:
                        chapter_sub_sources[title] = sub_sources
                        available_titles.append(title)
                    else:
                        # No sub-chapter text, fall back to full chapter
                        full_text = hierarchical_context.get_chapter_content(
                            doc_dir_name=doc_dir, chapter_title=title,
                        )
                        if full_text:
                            chapter_source_texts[title] = full_text
                        else:
                            # Fallback: ensure chapter enters parallel mode
                            chapter_source_texts[title] = ""
                            no_source_titles.append(title)
                        available_titles.append(title)
                else:
                    source_text = hierarchical_context.get_chapter_content(
                        doc_dir_name=doc_dir, chapter_title=title,
                    )
                    if source_text:
                        chapter_source_texts[title] = source_text
                    else:
                        # Fallback: ensure chapter enters parallel mode
                        chapter_source_texts[title] = ""
                        no_source_titles.append(title)
                    available_titles.append(title)

            # 8. Match section schemas for missing chapters
            from app.services.section_schemas import match_section_schema, SectionSchema
            chapter_schemas: Dict[str, Optional[SectionSchema]] = {}
            for mc in missing_chapters:
                title = mc.get("title", "")
                chapter_schemas[title] = match_section_schema(title)

            # 9. Build modification plan from chapter analysis (no extra LLM call needed)
            # The plan is simply the list of missing chapters — we already know
            # what to generate from the chapter index + source text extraction.
            retrieved_context_parts = []
            for title, text in chapter_source_texts.items():
                retrieved_context_parts.append(f"## {title}\n{text}")
            retrieved_context = "\n\n---\n\n".join(retrieved_context_parts) if retrieved_context_parts else ""

            missing_titles = [mc.get("title", "") for mc in missing_chapters]
            modification_plan = (
                f"基于知识库章节索引分析，初稿缺失以下章节，将从知识库原文补充：\n"
                + "\n".join(f"- {t}" for t in missing_titles)
            )

            # 9. 缓存以便后续确认使用
            self._collected_info["draft_id"] = draft_id
            self._collected_info["draft_content"] = draft_content
            self._collected_info["modification_plan"] = modification_plan
            self._collected_info["intent"] = intent
            self._collected_info["context"] = context
            self._collected_info["profile_context"] = profile_context
            self._collected_info["retrieved_context"] = retrieved_context
            self._collected_info["material_status"] = material_status
            self._collected_info["material_instruction"] = material_instruction
            self._collected_info["is_temp_upload"] = (
                draft_id is None
                and (bool(context.get("uploaded_file_content")) or force_all)
            )
            # Store chapter-level data for execution phase
            self._collected_info["missing_chapters"] = missing_chapters
            self._collected_info["chapter_source_texts"] = chapter_source_texts
            self._collected_info["chapter_sub_sources"] = chapter_sub_sources
            self._collected_info["chapter_schemas"] = chapter_schemas
            self._collected_info["generation_mode"] = context.get("generation_mode")

            # 9b. Load template and build chapter→template mapping
            template_data = None
            chapter_template_map: Dict[str, Dict[str, Any]] = {}
            try:
                from app.services.template_loader import (
                    load_template, match_chapter_by_title, get_fillable_slots,
                    get_chapter_by_code,
                )
                template_data = load_template("assembly_process_cable")
                for mc in missing_chapters:
                    title = mc.get("title", "")
                    tmpl_ch = match_chapter_by_title(title, template_data)
                    if tmpl_ch:
                        slots = get_fillable_slots(tmpl_ch)
                        chapter_template_map[title] = {
                            "chapter_code": tmpl_ch.code,
                            "chapter_type": tmpl_ch.table_type,
                            "template_slots": [
                                {
                                    "key": s.key,
                                    "label": s.label,
                                    "type": s.col_type,
                                    "fill_type": s.fill_type,
                                    "ai_filled": s.ai_filled,
                                }
                                for s in slots
                            ],
                            "ai_guidance": tmpl_ch.ai_guidance,
                        }
                logger.info(
                    "template_matched",
                    matched=len(chapter_template_map),
                    total=len(missing_chapters),
                    matched_titles=list(chapter_template_map.keys()),
                )
            except FileNotFoundError:
                logger.info("no_template_found, using markdown mode")
            except Exception as e:
                logger.warning("template_load_failed", error=str(e))

            self._collected_info["template"] = template_data
            self._collected_info["chapter_template_map"] = chapter_template_map

            # 10. 转到用户确认
            logger.info(
                "draft_complete_before_user_confirmation",
                current_state=self.state_machine.current_state.value,
                chapter_source_texts_count=len(chapter_source_texts),
                template_map_size=len(chapter_template_map),
            )
            await self.state_machine.transition_to(
                ProcessState.USER_CONFIRMATION,
                context_update={"modification_plan": modification_plan},
                trigger="plan_generated",
            )

            # 11. 暂停等待确认
            await self.state_machine.transition_to(
                ProcessState.PAUSED,
                trigger="awaiting_draft_plan_confirmation",
            )
            logger.info("draft_complete_now_paused", state=self.state_machine.current_state.value)

            return {
                "success": True,
                "requires_response": True,
                "interaction_type": "draft_plan_review",
                "draft_id": draft_id,
                "modification_plan": modification_plan,
                "material_status": material_status,
                "missing_chapters": [
                    {"title": mc.get("title", ""), "reason": mc.get("reason", "")}
                    for mc in missing_chapters
                ],
                "confirm_options": [
                    {"label": "确认执行", "value": "confirm"},
                    {"label": "需要调整", "value": "modify"},
                    {"label": "取消", "value": "cancel"},
                ],
                "state": self.state_machine.current_state.value,
            }

        except Exception as e:
            logger.error("draft_complete_failed", error=str(e))
            await self.state_machine.transition_to(ProcessState.ERROR, trigger="exception")
            return {
                "success": False,
                "error": str(e),
                "state": self.state_machine.current_state.value,
            }

    async def _detect_missing_chapters(
        self,
        chapter_summary: str,
        draft_content: str,
        user_requirement: str,
    ) -> List[Dict[str, Any]]:
        """Use LLM to compare chapter index against user draft and find missing chapters.

        Returns:
            List of {"title": str, "pages": [int], "_doc_dir": str, "page_count": int}
        """
        from app.services.hierarchical_context import hierarchical_context
        chapter_indexes = hierarchical_context.get_all_chapter_indexes()

        prompt = f"""你是工艺文件结构对比助手。请对比知识库文档的完整章节列表和用户的初稿，找出初稿中缺失的章节。

## 知识库文档完整章节列表
{chapter_summary}

## 用户初稿内容
{draft_content[:12000]}

## 用户需求
{user_requirement}

请输出一个 JSON 数组，每个元素代表一个初稿中确实缺失或内容不完整的章节：
```json
[
  {{"chapter": "章节名称", "reason": "缺失原因"}}
]
```

要求：
- 只列出初稿中确实缺失或内容严重不完整的章节
- 不要列已有完整内容的章节
- 如果没有缺失，输出空数组 []
- 只输出 JSON，不要输出其他内容"""

        try:
            from app.services.llm_service import llm_service
            result = await llm_service.generate_with_messages(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
                tier="simple",
            )
            if result.get("status") == "error":
                logger.warning("missing_chapter_detection_llm_failed", error=result.get("error"))
                return self._fallback_missing_detection(chapter_indexes, draft_content)

            content = result.get("content", "").strip()
            # Strip markdown code fences
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()

            import json as _json
            detected = _json.loads(content)
            if not isinstance(detected, list):
                return []

            # Map detected chapter names back to index entries
            missing = []
            for item in detected:
                ch_name = item.get("chapter", "")
                for idx in chapter_indexes:
                    for ch in idx.get("chapters", []):
                        if ch_name in ch["title"] or ch["title"] in ch_name:
                            missing.append({
                                "title": ch["title"],
                                "pages": ch["pages"],
                                "page_count": ch["page_count"],
                                "sub_chapters": ch.get("sub_chapters", []),
                                "_doc_dir": idx.get("_doc_dir", ""),
                                "reason": item.get("reason", ""),
                            })
                            break

            return missing

        except Exception as e:
            logger.warning("missing_chapter_detection_failed", error=str(e))
            return self._fallback_missing_detection(chapter_indexes, draft_content)

    def _fallback_missing_detection(
        self,
        chapter_indexes: List[Dict[str, Any]],
        draft_content: str,
    ) -> List[Dict[str, Any]]:
        """Fallback: mark all chapters as missing if LLM detection fails."""
        missing = []
        for idx in chapter_indexes:
            for ch in idx.get("chapters", []):
                # Simple heuristic: check if chapter title appears in draft
                if ch["title"] not in draft_content:
                    missing.append({
                        "title": ch["title"],
                        "pages": ch["pages"],
                        "page_count": ch["page_count"],
                        "sub_chapters": ch.get("sub_chapters", []),
                        "_doc_dir": idx.get("_doc_dir", ""),
                        "reason": "章节标题未出现在初稿中",
                    })
        return missing

    async def _load_profile_context(self, context: Dict[str, Any]) -> str:
        """加载用户画像上下文

        Args:
            context: 会话上下文

        Returns:
            画像上下文字符串
        """
        try:
            from app.services.context_service import ContextService

            base_path = context.get("base_path", ".")
            user_id = context.get("user_id", "default")
            domain = context.get("domain", "assembly")

            cs = ContextService(base_path=base_path)
            profile = cs.load_profile(user_id=user_id, domain=domain)

            # 构建画像上下文
            profile_ctx = (
                f"领域: {profile.domain}\n"
                f"写作风格: {profile.writing.tone}\n"
                f"术语库: {profile.writing.terminology}\n"
                f"详细程度: {profile.writing.detail_level}"
            )
            return profile_ctx

        except Exception as e:
            logger.warning("profile_load_failed, using defaults", error=str(e))
            return "领域: assembly\n写作风格: 专业严谨\n术语库: 企业标准术语\n详细程度: 详细"

    async def _build_retrieval_context(self, query: str, context: Dict[str, Any]) -> tuple:
        """构建检索上下文，同时返回素材状态摘要

        尝试使用 LLMContextService；如果不可用，回退到 HierarchicalContext。

        Args:
            query: 检索查询
            context: 会话上下文

        Returns:
            (retrieved_context: str, material_status: dict)
        """
        try:
            from app.services.hierarchical_context import hierarchical_context

            session_id = context.get("session_id", self.current_task_id or "default")
            rag_ctx = hierarchical_context.build_context(query=query, session_id=session_id, max_tokens=8000)

            # Get material status
            material_status = hierarchical_context.get_material_status(query)

            return rag_ctx or "（未检索到相关参考资料）", material_status

        except Exception as e:
            logger.warning("retrieval_context_build_failed", error=str(e))
            return "（检索服务不可用）", {"has_documents": False, "document_count": 0, "documents": [], "search_performed": False, "missing_topics": []}

    def _build_material_status_instruction(self, material_status: Dict[str, Any]) -> str:
        """Build instruction text based on material status for Agent context injection.

        Three decision paths:
        1. No documents → tell user to upload first
        2. Partial coverage → list what's missing and what's available
        3. Sufficient → proceed with high confidence

        Args:
            material_status: Material status dict from HierarchicalContext

        Returns:
            Instruction string to inject into Agent context
        """
        if not material_status.get("has_documents"):
            return (
                "【素材状态指令】系统当前没有任何可用素材文档。"
                "请在回复中明确告知用户：系统暂无参考资料，请先通过素材库上传相关工艺文件（PDF/Word），"
                "上传后系统会自动解析内容供后续使用。"
            )

        missing = material_status.get("missing_topics", [])
        doc_names = [d.get("name", "") for d in material_status.get("documents", [])]
        doc_list_str = "、".join(doc_names) if doc_names else "无"

        if missing and len(missing) >= 2:
            missing_str = "、".join(missing[:5])
            return (
                f"【素材状态指令】当前有 {material_status.get('document_count', 0)} 个参考文档"
                f"（{doc_list_str}），但用户查询涉及的内容中，以下主题在已有素材中可能未充分覆盖："
                f"{missing_str}。"
                "请在回复中：(1) 基于已有素材提供能确定的部分；"
                f"(2) 明确指出哪些内容因缺少参考素材而无法确认，建议用户补充上传相关文档。"
            )

        return (
            f"【素材状态指令】素材充足，当前有 {material_status.get('document_count', 0)} 个参考文档"
            f"（{doc_list_str}），覆盖了用户查询的主要内容。"
            "请基于这些素材高置信度地执行任务。如果有不确定的地方，列出2-3个具体方案让用户确认。"
        )

    async def _load_draft_content(self, context: Dict[str, Any]) -> tuple:
        """加载初稿内容

        优先使用上下文中的 draft_id，否则尝试使用最新初稿。

        Args:
            context: 会话上下文

        Returns:
            (draft_content: str | None, draft_id: int | None)
        """
        draft_id = context.get("draft_id")

        if draft_id is None:
            # 无 draft_id，返回 None
            return None, None

        try:
            from app.services.draft_service import DraftService
            from app.models.database import get_db

            db = next(get_db())
            try:
                ds = DraftService(db)
                draft = ds.get_draft(draft_id)
                if draft is None:
                    return None, draft_id
                return draft.content, draft.id
            finally:
                db.close()

        except Exception as e:
            logger.error("draft_load_failed", draft_id=draft_id, error=str(e))
            return None, draft_id

    async def _generate_modification_plan(
        self,
        profile_context: str,
        retrieved_context: str,
        draft_content: str,
        user_requirement: str,
        material_instruction: str = "",
    ) -> str:
        """调用 LLM 生成修改方案

        Args:
            profile_context: 用户画像上下文
            retrieved_context: 检索到的参考资料
            draft_content: 初稿内容
            user_requirement: 用户需求
            material_instruction: Material status instruction from Orchestrator

        Returns:
            修改方案文本
        """
        material_section = ""
        if material_instruction:
            material_section = f"\n## 素材状态指令\n{material_instruction}\n"

        prompt = f"""你是工艺文件编辑助手。用户上传了一份不完整的工艺文件，需要你对比知识库中的完整文档，制定修改方案。

{material_section}
## 用户画像
{profile_context}

## 知识库中的参考资料
{retrieved_context}

## 用户上传的初稿
{draft_content[:12000]}

## 用户需求
{user_requirement}

请完成以下两项任务：

### 任务1：修改方案文本
逐个模块对比初稿和知识库文档，列出每个缺失或需要补充的模块。对每个缺失模块写明：模块名称 + 需要补充的具体内容（关键参数、表格、步骤等）。如果知识库有对应完整内容，标注「知识库有原文」；如果知识库也没有，标注「待用户确认」。

### 任务2：结构化模块列表（必须放在末尾）
在方案文本的最后，用 `---MODULES---` 作为分隔符，然后输出一个 JSON 数组。每个元素代表一个需要补充（缺失或部分缺失）的模块：

```json
[
  {{"name": "模块名称", "status": "缺失或部分缺失", "source": "知识库有原文或待用户确认", "instruction": "补充的具体指令"}}
]
```

要求：
- 只列出初稿中**确实缺失或需要补充**的模块，不要列已有完整内容的模块
- instruction 要具体：写明需要补充哪些表格、参数、步骤等
- 如果没有任何模块缺失，输出空数组 []
- 不要写分析过程、不要写通用建议、不要重复已有内容
"""

        try:
            from app.services.deepseek_service import DeepSeekService

            ds = DeepSeekService()
            if ds.is_available:
                result = await ds.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=4000,
                )
                if result.get("status") == "success":
                    return result["content"]
                logger.warning("deepseek_chat_failed", error=result.get("error"))
        except Exception as e:
            logger.warning("deepseek_generation_failed", error=str(e))

        # 最终回退：返回结构化的提示
        return (
            "⚠️ LLM 服务暂不可用，以下是基于现有信息的初步建议：\n\n"
            f"**用户需求**: {user_requirement}\n\n"
            "请根据检索到的参考资料和画像要求，手动确认修改方案。"
        )

    def _parse_modules_from_plan(self, plan_text: str) -> List[Dict[str, str]]:
        """Parse structured module list from modification plan text.

        Looks for a ``---MODULES---`` delimiter in the plan, then extracts
        the JSON array that follows it.  Returns a list of dicts with keys
        ``name``, ``status``, ``source``, ``instruction``.  Returns an empty
        list on any parse failure (caller falls back to single-task mode).
        """
        import json as _json

        delimiter = "---MODULES---"
        idx = plan_text.find(delimiter)
        if idx == -1:
            logger.info("modules_delimiter_not_found")
            return []

        json_part = plan_text[idx + len(delimiter):].strip()
        # Strip markdown code fences if present
        if json_part.startswith("```"):
            lines = json_part.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            json_part = "\n".join(lines).strip()

        try:
            modules = _json.loads(json_part)
            if isinstance(modules, list) and all(
                isinstance(m, dict) and "name" in m and "instruction" in m
                for m in modules
            ):
                logger.info("modules_parsed", count=len(modules))
                return modules
            logger.warning("modules_json_invalid_structure")
            return []
        except _json.JSONDecodeError:
            logger.warning("modules_json_parse_failed", snippet=json_part[:200])
            return []

    async def _execute_draft_modification(self) -> Dict[str, Any]:
        """Execute a confirmed draft modification plan.

        Supports two modes:

        1. **Chapter-based parallel mode** — when chapter_source_texts are
           available, each missing chapter is dispatched as an independent
           WritingAgent task with its own source text.  All tasks run in
           parallel via ``asyncio.gather`` and results are spliced in order.
        2. **Module-based mode** — fallback using ---MODULES--- from plan.
        3. **Single-task fallback** — if no structured modules are found.
        """
        draft_id = self._collected_info.get("draft_id")
        modification_plan = self._collected_info.get("modification_plan", "")
        draft_content = self._collected_info.get("draft_content", "")
        profile_context = self._collected_info.get("profile_context", "")
        retrieved_context = self._collected_info.get("retrieved_context", "")
        material_instruction = self._collected_info.get("material_instruction", "")
        intent = self._collected_info.get("intent", {})
        is_temp_upload = self._collected_info.get("is_temp_upload", False)
        chapter_source_texts: Dict[str, str] = self._collected_info.get("chapter_source_texts", {})
        chapter_sub_sources: Dict[str, Dict[str, str]] = self._collected_info.get("chapter_sub_sources", {})
        chapter_schemas: Dict[str, Any] = self._collected_info.get("chapter_schemas", {})
        template = self._collected_info.get("template")
        chapter_template_map: Dict[str, Dict[str, Any]] = self._collected_info.get("chapter_template_map", {})
        modules: List[Dict[str, str]] = []

        if not draft_id and not is_temp_upload:
            return {"success": False, "error": "缺少 draft_id"}

        # 1. Task decomposition
        logger.info(
            "execute_draft_modification_entry",
            current_state=self.state_machine.current_state.value,
            chapter_source_texts_count=len(chapter_source_texts),
            has_template=template is not None,
            template_map_size=len(chapter_template_map or {}),
        )
        transition_ok = await self.state_machine.transition_to(
            ProcessState.TASK_DECOMPOSITION,
            trigger="draft_plan_confirmed",
        )
        logger.info("task_decomposition_transition", success=transition_ok, state_after=self.state_machine.current_state.value)

        # 2. Try chapter-based parallel generation first
        # Fallback: when template_map has entries but source_texts is empty,
        # populate from template_map keys so we still enter parallel + template fill path
        if not chapter_source_texts and chapter_template_map:
            logger.info(
                "chapter_source_texts_empty_using_template_fallback",
                template_chapters=list(chapter_template_map.keys()),
            )
            for title in chapter_template_map:
                chapter_source_texts[title] = ""

        if chapter_source_texts:
            logger.info("executing_chapters_parallel", chapters=list(chapter_source_texts.keys()), template=bool(template), template_map_size=len(chapter_template_map or {}))
            new_content, structured_results = await self._execute_chapters_parallel(
                chapter_source_texts=chapter_source_texts,
                chapter_sub_sources=chapter_sub_sources,
                draft_content=draft_content,
                material_instruction=material_instruction,
                chapter_schemas=chapter_schemas,
                template=template,
                chapter_template_map=chapter_template_map,
            )
            agent_result = {
                "status": "completed",
                "result": {"content": new_content},
            }
        else:
            structured_results = {}
            # 3. Fallback: parse structured modules from plan
            modules = self._parse_modules_from_plan(modification_plan)

            if modules:
                # --- Module-based parallel mode ---
                new_content = await self._execute_modules_parallel(
                    modules=modules,
                    draft_content=draft_content,
                    retrieved_context=retrieved_context,
                    material_instruction=material_instruction,
                    profile_context=profile_context,
                )
                agent_result = {
                    "status": "completed",
                    "result": {"content": new_content},
                }
            else:
                # --- Single-task fallback (original logic) ---
                writing_task = {
                    "type": "writing",
                    "action": "generate",
                    "content": modification_plan,
                    "target": "工艺文件完善",
                    "requirements": "请按修改方案，逐章补充缺失内容，输出完整工艺文件。",
                    "params": {
                        "retrieved_context": retrieved_context,
                        "draft_content": draft_content,
                        "modification_plan": modification_plan,
                        "material_instruction": material_instruction,
                        "skip_planning": True,
                    },
                    "generate_doc": False,
                }

                await self.state_machine.transition_to(
                    ProcessState.TASK_EXECUTION,
                    trigger="draft_tasks_decomposed",
                )

                agent_result = await self._dispatch_to_sub_agent(writing_task)

        # 3. Extract content from result
        new_content = None
        if agent_result.get("status") == "completed":
            inner = agent_result.get("result", {})
            if isinstance(inner, dict):
                new_content = inner.get("content") or inner.get("result", {}).get("content")

        # 4. Save result to draft
        # Also assemble structured content.json v2 + content.html when
        # chapter-based parallel mode was used.
        structured_result = None
        if new_content:
            # Assemble structured JSON v2 from Markdown output
            if chapter_source_texts:
                try:
                    from app.services.content_assembler import (
                        assemble_content_json,
                        generate_content_html,
                    )
                    material_id = str(draft_id) if draft_id else "temp"
                    # Determine chapters generated without reference source
                    missing_chs = self._collected_info.get("missing_chapters", [])
                    no_src_titles = [
                        mc.get("title", "") for mc in missing_chs
                        if not mc.get("_doc_dir", "")
                    ]
                    content_json = assemble_content_json(
                        new_content, material_id, no_source_titles=no_src_titles,
                    )
                    structured_result = content_json

                    # Generate HTML from structured JSON
                    content_html = generate_content_html(content_json)

                    # Save structured files alongside the draft
                    if draft_id and not is_temp_upload:
                        try:
                            from app.services.content_assembler import save_content_files
                            paths = save_content_files(content_json, material_id)
                            logger.info(
                                "structured_content_saved",
                                json_path=paths.get("json_path"),
                                html_path=paths.get("html_path"),
                            )
                        except Exception as e:
                            logger.warning("structured_content_save_failed", error=str(e))

                    # Also update draft with the HTML version
                    if draft_id and not is_temp_upload:
                        try:
                            from app.services.draft_service import DraftService
                            from app.models.database import get_db

                            db = next(get_db())
                            try:
                                ds = DraftService(db)
                                ds.update_content(draft_id, content_html, source="ai_structured")
                            finally:
                                db.close()
                        except Exception as e:
                            logger.error("structured_draft_save_failed", draft_id=draft_id, error=str(e))

                except Exception as e:
                    logger.warning("content_assembly_failed", error=str(e))

            if draft_id and not is_temp_upload:
                try:
                    from app.services.draft_service import DraftService
                    from app.models.database import get_db

                    db = next(get_db())
                    try:
                        ds = DraftService(db)
                        ds.update_content(draft_id, new_content, source="ai_draft_complete")
                    finally:
                        db.close()
                except Exception as e:
                    logger.error("draft_save_failed", draft_id=draft_id, error=str(e))
            else:
                logger.info("draft_complete_temp_upload", content_length=len(new_content))

        # 5. Aggregate results
        await self.state_machine.transition_to(
            ProcessState.RESULT_AGGREGATION,
            trigger="draft_execution_completed",
        )

        # 6. Complete
        await self.state_machine.transition_to(
            ProcessState.COMPLETION,
            trigger="draft_aggregation_complete",
        )

        # Clear cache
        self._collected_info.clear()

        return {
            "success": True,
            "task_id": self.current_task_id,
            "intent": intent,
            "draft_id": draft_id,
            "result": {
                "agent_result": agent_result,
                "content_updated": new_content is not None,
                "chapters_generated": len(chapter_source_texts),
                "modules_generated": len(modules) if modules else 0,
                "structured_content": structured_result,
                "structured_results": structured_results,
            },
            "state": self.state_machine.current_state.value,
        }

    async def _execute_chapters_parallel(
        self,
        chapter_source_texts: Dict[str, str],
        chapter_sub_sources: Dict[str, Dict[str, str]],
        draft_content: str,
        material_instruction: str,
        chapter_schemas: Optional[Dict[str, Any]] = None,
        template: Optional[Dict[str, Any]] = None,
        chapter_template_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple:
        """Dispatch one WritingAgent task per chapter with source text in parallel.

        Each chapter gets its own source text from the knowledge base,
        preventing the LLM from fabricating content.

        When template + chapter_template_map are provided, matching chapters
        use _do_template_fill for structured JSON output instead of Markdown.

        Returns:
            Tuple of (markdown_content, structured_results_dict).
            structured_results_dict maps chapter_code to filled data.
        """
        await self.state_machine.transition_to(
            ProcessState.TASK_EXECUTION,
            trigger="draft_tasks_decomposed",
        )

        # Resolve correct chapter order from knowledge base index
        from app.services.hierarchical_context import hierarchical_context
        ordered_titles: List[str] = []
        all_indexes = hierarchical_context.get_all_chapter_indexes()
        title_set = set(chapter_source_texts.keys())
        for idx in all_indexes:
            for ch in idx.get("chapters", []):
                if ch["title"] in title_set:
                    ordered_titles.append(ch["title"])

        # Fall back to chapter_source_texts order if index lookup yields nothing
        if not ordered_titles:
            ordered_titles = list(chapter_source_texts.keys())

        # Append any chapters not found in the index (e.g. no-source chapters)
        index_set = set(ordered_titles)
        for t in chapter_source_texts:
            if t not in index_set:
                ordered_titles.append(t)

        # Deduplicate while preserving order
        seen = set()
        unique_titles: List[str] = []
        for t in ordered_titles:
            if t not in seen:
                seen.add(t)
                unique_titles.append(t)

        # Build tasks in correct chapter order.
        # For large chapters with sub-chapters, create one task per sub-chapter.
        tasks = []
        task_keys: List[str] = []  # "title" or "title::sub_title"
        for title in unique_titles:
            # Resolve schema for this chapter (if any)
            schema = chapter_schemas.get(title) if chapter_schemas else None

            sub_sources = chapter_sub_sources.get(title)
            if sub_sources:
                # Split into sub-chapter tasks
                for sub_title, sub_text in sub_sources.items():
                    key = f"{title}::{sub_title}"
                    task = {
                        "type": "writing",
                        "action": "generate",
                        "content": f"生成「{sub_title}」内容",
                        "target": f"{sub_title}",
                        "requirements": f"参考知识库文档生成「{sub_title}」的完整内容",
                        "params": {
                            "chapter_source_text": sub_text,
                            "module_name": sub_title,
                            "section_schema": schema,
                            "module_instruction": (
                                f"你是工艺文件编写专家。以下是知识库文档中「{sub_title}」的参考文档"
                                "（包含完整的工序内容、材料和参数）。\n"
                                "\n"
                                "要求：\n"
                                "1. 参考知识库文档的格式和术语体系，根据工艺要求整理为规范的工艺文件\n"
                                "2. 保留原文中的关键参数、代号、材料名称和数量，不得编造不存在的数据\n"
                                "3. 如果原文包含表格数据（工艺参数表、材料清单等），以表格形式完整输出\n"
                                "4. 如果原文包含技术条件、公差要求、表面粗糙度等数值，必须保留\n"
                                "5. 每道工序应包含：工序名称、设备/工具、操作内容、检验要求（如原文有）\n"
                                "6. 工序必须严格按编号顺序输出，不允许跳跃或省略\n"
                                "7. 内容必须详实完整，不得因篇幅原因省略或概括原文中的具体内容\n"
                                "8. 不要输出分析过程、来源说明、页码引用或对原文内容的点评"
                            ),
                            "skip_planning": True,
                        },
                        "generate_doc": False,
                    }
                    tasks.append(task)
                    task_keys.append(key)
            else:
                # Normal single chapter task
                source_text = chapter_source_texts[title]
                has_source = bool(source_text and source_text.strip())

                if has_source:
                    instruction = (
                        f"你是工艺文件编写专家。请参考以下知识库文档，生成「{title}」章节的完整、详细的工艺文件内容。\n"
                        "\n"
                        "要求：\n"
                        "1. 参考知识库文档的格式和术语体系，根据工艺要求生成内容\n"
                        "2. 保留原文中的关键参数、代号、材料名称和数量，不得编造不存在的数据\n"
                        "3. 保留原文中所有工序号、工步号，按编号顺序输出，不允许跳跃或省略\n"
                        "4. 如果原文包含表格数据（如工艺参数表、材料清单等），以表格形式完整输出\n"
                        "5. 如果原文包含技术条件、公差要求、表面粗糙度等数值，必须保留\n"
                        "6. 每道工序应包含：工序名称、设备/工具、操作内容、检验要求（如原文有）\n"
                        "7. 内容必须详实完整，不得因篇幅原因省略或概括原文中的具体内容\n"
                        "8. 不要输出分析过程、来源说明、页码引用或对原文内容的点评\n"
                        "9. 格式要求：标题用粗体，工序号独立成行，参数和数值用等宽格式"
                    )
                else:
                    # No source text — generate from overall draft context
                    instruction = (
                        f"你是工艺文件编写专家。请根据已有的工艺文件上下文，生成「{title}」章节的完整内容。\n"
                        "\n"
                        f"该章节在知识库中没有对应的原文，但根据工艺文件的标准结构，"
                        f"「{title}」是工艺文件的必要组成部分。\n"
                        "\n"
                        "要求：\n"
                        "1. 参考已有章节的格式、术语和参数风格，保持全文一致\n"
                        "2. 如果能从上下文推断出相关参数，直接使用；不确定的用 [待确认] 标注\n"
                        "3. 如果包含工序内容，每道工序应包含：工序名称、设备/工具、操作内容、检验要求\n"
                        "4. 如果包含表格数据，以表格形式输出\n"
                        "5. 内容要详实具体，不要写空泛的描述，宁可标注[待确认]也不要写无意义的填充内容\n"
                        "6. 不要输出分析过程或说明性文字，直接输出工艺文件正文"
                    )

                task = {
                    "type": "writing",
                    "action": "generate",
                    "content": f"生成「{title}」章节内容",
                    "target": title,
                    "requirements": f"参考知识库文档生成「{title}」章节的完整内容",
                    "params": {
                        "chapter_source_text": source_text if has_source else draft_content,
                        "module_name": title,
                        "section_schema": schema,
                        "module_instruction": instruction,
                        "skip_planning": True,
                    },
                    "generate_doc": False,
                }

                # Inject template slots for structured JSON output
                tmpl_info = (chapter_template_map or {}).get(title)
                if tmpl_info and tmpl_info.get("template_slots"):
                    task["template_slots"] = tmpl_info["template_slots"]
                    task["chapter_code"] = tmpl_info["chapter_code"]
                    task["chapter_type"] = tmpl_info["chapter_type"]
                    task["chapter_title"] = title
                    task["ai_guidance"] = tmpl_info.get("ai_guidance", "")

                tasks.append(task)
                task_keys.append(title)

        logger.info(
            "chapter_parallel_dispatching",
            task_count=len(tasks),
            tasks=task_keys,
        )

        coros = [self._dispatch_to_sub_agent(t) for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # --- Review-Retry (workflow #4: incomplete PDF completion) ---
        # Check each chapter output with ReviewAgent. Retry once if issues found.
        from app.agents.functional.review_agent import ReviewAgent
        _reviewer = ReviewAgent()

        retry_indices: List[int] = []
        retry_tasks: List[Dict[str, Any]] = []
        retry_coros = []

        for i, (key, result) in enumerate(zip(task_keys, results)):
            if isinstance(result, BaseException):
                continue
            if not (isinstance(result, dict) and result.get("status") == "completed"):
                continue
            inner = result.get("result", {})
            if not isinstance(inner, dict):
                continue
            content = inner.get("content") or inner.get("result", {}).get("content", "")
            if not content:
                continue

            # Resolve schema for this chapter to enable table structure validation
            chapter_schema = tasks[i]["params"].get("section_schema")
            # Lenient mode for chapters generated without reference source
            chapter_source = tasks[i]["params"].get("chapter_source_text", "")
            is_no_source = not bool(chapter_source and chapter_source.strip())
            quality = _reviewer._check_output_quality(
                content, section_schema=chapter_schema, lenient=is_no_source,
            )
            if quality.get("passed"):
                continue

            warnings_text = [w.get("message", str(w)) for w in quality.get("warnings", [])]
            logger.info("chapter_quality_retry", key=key, warnings=warnings_text)

            module_name = tasks[i]["params"].get("module_name", key)
            source_text = tasks[i]["params"].get("chapter_source_text", "")
            correction = (
                "你上一次输出存在以下问题，请修正后重新输出（只输出修正后的内容，不要解释）：\n"
                + "\n".join(f"- {w}" for w in warnings_text)
            )

            retry_task = {
                "type": "writing",
                "action": "generate",
                "content": f"修正「{module_name}」内容",
                "target": module_name,
                "params": {
                    **tasks[i]["params"],
                    "module_instruction": correction,
                    "retry_context": content,
                },
                "generate_doc": False,
            }
            retry_indices.append(i)
            retry_tasks.append(retry_task)
            retry_coros.append(self._dispatch_to_sub_agent(retry_task))

        if retry_coros:
            logger.info("chapter_retries_dispatching", count=len(retry_coros))
            retry_results = await asyncio.gather(*retry_coros, return_exceptions=True)
            for j, orig_idx in enumerate(retry_indices):
                rr = retry_results[j]
                if isinstance(rr, dict) and rr.get("status") == "completed":
                    inner = rr.get("result", {})
                    retry_content = ""
                    if isinstance(inner, dict):
                        retry_content = inner.get("content") or inner.get("result", {}).get("content", "")
                    if retry_content:
                        results[orig_idx] = rr
                        logger.info("chapter_retry_success", key=task_keys[orig_idx], length=len(retry_content))

        # Collect structured template results before building Markdown
        structured_results: Dict[str, Any] = {}
        if template and chapter_template_map:
            for i, (key, result) in enumerate(zip(task_keys, results)):
                if isinstance(result, BaseException):
                    continue
                if not (isinstance(result, dict) and result.get("status") == "completed"):
                    continue
                inner = result.get("result", {})
                if not isinstance(inner, dict):
                    continue
                # Check if this was a template_fill result
                if inner.get("chapter_code"):
                    structured_results[inner["chapter_code"]] = inner
                elif inner.get("result", {}).get("chapter_code"):
                    structured_results[inner["result"]["chapter_code"]] = inner["result"]

        # Template mode: skip Markdown assembly, return structured data only
        if structured_results:
            logger.info(
                "template_results_only",
                chapters=len(structured_results),
                total_tasks=len(task_keys),
            )
            return "", structured_results

        # Fallback: build Markdown output (no template matched)
        # Build output in correct chapter order.
        # Sub-chapter results are grouped under their parent chapter.
        parts: List[str] = []
        splice_log = []

        # Group results by parent chapter
        current_parent: Optional[str] = None
        sub_parts: List[str] = []

        for key, result in zip(task_keys, results):
            # Determine parent title and sub-title
            if "::" in key:
                parent_title, sub_title = key.split("::", 1)
            else:
                parent_title = key
                sub_title = None

            # Flush previous parent's sub-chapters if parent changed
            if parent_title != current_parent:
                if sub_parts:
                    parts.append(f"## {current_parent}\n\n" + "\n\n".join(sub_parts))
                    sub_parts = []
                current_parent = parent_title

            # Extract content from result
            content = ""
            if isinstance(result, BaseException):
                logger.error("chapter_generation_failed", key=key, error=str(result))
                content = f"[待确认：{sub_title or parent_title} 生成失败，请手动补充]"
                splice_log.append({"key": key, "status": "error"})
            elif isinstance(result, dict) and result.get("status") == "completed":
                inner = result.get("result", {})
                if isinstance(inner, dict):
                    content = inner.get("content") or inner.get("result", {}).get("content", "")

            if content:
                # Strip duplicate heading from WritingAgent output
                # WritingAgent may start with "### {module_name}" which duplicates
                # the "## {parent_title}" we prepend
                content = _strip_duplicate_heading(content, parent_title)
                if sub_title:
                    # Sub-chapter: let WritingAgent output stand on its own
                    sub_parts.append(content)
                else:
                    parts.append(f"## {parent_title}\n\n{content}")
                splice_log.append({"key": key, "status": "ok", "length": len(content)})
            else:
                if sub_title:
                    sub_parts.append(f"### {sub_title}\n\n[待确认：内容未能生成]")
                else:
                    parts.append(f"## {parent_title}\n\n[待确认：章节内容未能生成]")
                splice_log.append({"key": key, "status": "empty"})

        # Flush remaining sub-chapters
        if sub_parts:
            parts.append(f"## {current_parent}\n\n" + "\n\n".join(sub_parts))

        final_content = "\n\n---\n\n".join(parts)

        # Post-process: strip [待确认] noise from LLM output.
        # Our structured markers use [待确认：...] (with colon), keep those.
        # Only remove bare [待确认] lines that the LLM adds as disclaimers.
        final_content = _re.sub(
            r"\n*\[待确认\]\s*\n",
            "\n",
            final_content,
        )
        # Also remove trailing [待确认] at end of content blocks
        final_content = _re.sub(
            r"\[待确认\]\s*$",
            "",
            final_content,
            flags=_re.MULTILINE,
        )

        # Strip signature/date rows — these are template fields filled on export.
        # Patterns: "编制 牛一凡 20240826", "审核 崔兴斌 20240827",
        # "校对/审核/标检/批准/会签 ... date", "共N页第N页",
        # standalone lines with just a name + date stamp.
        final_content = _re.sub(
            r"^[ \t]*(?:编制|校对|审核|标检|批准|会签)[ \t]+\S+.*$",
            "",
            final_content,
            flags=_re.MULTILINE,
        )
        # "阶段标记 S2" lines
        final_content = _re.sub(
            r"^[ \t]*阶段标记.*$",
            "",
            final_content,
            flags=_re.MULTILINE,
        )
        # "共N页第N页" footer lines
        final_content = _re.sub(
            r"^[ \t]*共\d+页[ \t]*第\d+页.*$",
            "",
            final_content,
            flags=_re.MULTILINE,
        )
        # Collapse excessive blank lines (3+ → 2)
        final_content = _re.sub(r"\n{3,}", "\n\n", final_content)

        logger.info(
            "chapter_parallel_complete",
            total_tasks=len(task_keys),
            final_length=len(final_content),
            splice_detail=splice_log,
        )

        # Final quality stats (chapters already reviewed individually above)
        try:
            final_quality = _reviewer._check_output_quality(final_content)
            logger.info(
                "final_quality_check",
                passed=final_quality.get("passed"),
                warnings_count=len(final_quality.get("warnings", [])),
            )
        except Exception as e:
            logger.warning("final_quality_check_error", error=str(e))

        return final_content, structured_results

    async def _execute_modules_parallel(
        self,
        modules: List[Dict[str, str]],
        draft_content: str,
        retrieved_context: str,
        material_instruction: str,
        profile_context: str,
    ) -> str:
        """Dispatch one WritingAgent task per module in parallel, then splice.

        Returns the combined content string (existing draft + all module
        supplements) ready to be saved or returned.
        """
        await self.state_machine.transition_to(
            ProcessState.TASK_EXECUTION,
            trigger="draft_tasks_decomposed",
        )

        # Build one task per module
        tasks = []
        for mod in modules:
            task = {
                "type": "writing",
                "action": "generate",
                "content": mod["instruction"],
                "target": mod["name"],
                "requirements": f"生成模块「{mod['name']}」的完整内容。{mod['instruction']}",
                "params": {
                    "retrieved_context": retrieved_context,
                    "module_name": mod["name"],
                    "module_instruction": mod["instruction"],
                    "skip_planning": True,
                },
                "generate_doc": False,
            }
            tasks.append(task)

        logger.info(
            "parallel_modules_dispatching",
            module_count=len(tasks),
            modules=[m["name"] for m in modules],
        )

        # Execute all module tasks in parallel
        coros = [self._dispatch_to_sub_agent(t) for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Splice: existing draft content + each module's output in order
        parts = [draft_content] if draft_content else []
        splice_log = []
        for mod, result in zip(modules, results):
            if isinstance(result, BaseException):
                logger.error(
                    "module_generation_failed",
                    module=mod["name"],
                    error=str(result),
                )
                parts.append(f"\n\n## {mod['name']}\n\n[待确认：模块生成失败，请手动补充]")
                splice_log.append({"module": mod["name"], "status": "error", "error": str(result)})
                continue

            if isinstance(result, dict) and result.get("status") == "completed":
                inner = result.get("result", {})
                if isinstance(inner, dict):
                    content = inner.get("content") or inner.get("result", {}).get("content", "")
                    if content:
                        parts.append(f"\n\n## {mod['name']}\n\n{content}")
                        splice_log.append({"module": mod["name"], "status": "ok", "length": len(content)})
                        continue

            parts.append(f"\n\n## {mod['name']}\n\n[待确认：模块内容未能生成]")
            splice_log.append({"module": mod["name"], "status": "empty"})

        final_content = "\n".join(parts)

        # Post-process: strip bare [待确认] noise from LLM output
        final_content = _re.sub(r"\n*\[待确认\]\s*\n", "\n", final_content)
        final_content = _re.sub(r"\[待确认\]\s*$", "", final_content, flags=_re.MULTILINE)

        logger.info(
            "parallel_modules_complete",
            total_modules=len(modules),
            final_length=len(final_content),
            splice_detail=splice_log,
        )
        return final_content

    async def _execute_confirmed_task(self) -> Dict[str, Any]:
        """执行已确认的任务"""
        intent = self._collected_info.get("intent", {})
        context = self._collected_info.get("context", {})

        # 分解任务
        await self.state_machine.transition_to(
            ProcessState.TASK_DECOMPOSITION,
            trigger="user_confirmed"
        )

        tasks = await self.task_decomposer.decompose(intent)
        logger.info("tasks_decomposed", task_count=len(tasks))

        # 执行任务
        await self.state_machine.transition_to(
            ProcessState.TASK_EXECUTION,
            trigger="tasks_decomposed"
        )

        results = []
        for task in tasks:
            agent_result = await self._dispatch_to_sub_agent(task)
            results.append(agent_result)

        # 聚合结果
        await self.state_machine.transition_to(
            ProcessState.RESULT_AGGREGATION,
            trigger="all_tasks_completed"
        )

        aggregated_result = await self._aggregate_results(results)

        # 完成
        await self.state_machine.transition_to(
            ProcessState.COMPLETION,
            trigger="aggregation_complete"
        )

        # 清理缓存
        self._collected_info.clear()

        return {
            "success": True,
            "task_id": self.current_task_id,
            "intent": intent,
            "result": aggregated_result,
            "state": self.state_machine.current_state.value,
        }

    async def continue_conversation(
        self,
        user_response: UserResponse
    ) -> Dict[str, Any]:
        """
        继续对话（用户补充信息后）

        Args:
            user_response: 用户响应

        Returns:
            下一步的交互消息或执行结果
        """
        return await self._handle_user_response(user_response)

    async def proofread_only(
        self,
        content: str,
        check_type: str = "all",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        仅执行校对（独立调用校对Agent）

        Args:
            content: 待校对内容
            check_type: 检查类型 (terminology/data/format/all)
            context: 执行上下文

        Returns:
            校对结果
        """
        if "proofread" not in self._agents:
            return {"success": False, "error": "校对Agent不可用"}

        agent = self._agents["proofread"]
        task = {
            "content": content,
            "check_type": check_type,
        }

        result = await agent.process(task, context)
        logger.info("proofread_only_completed", check_type=check_type)

        return result

    async def review_only(
        self,
        content: str,
        check_type: str = "all",
        standards: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        仅执行审查（独立调用审查Agent）

        Args:
            content: 待审查内容
            check_type: 检查类型 (compliance/rationality/risk/all)
            standards: 要检查的标准列表
            context: 执行上下文

        Returns:
            审查结果
        """
        if "review" not in self._agents:
            return {"success": False, "error": "审查Agent不可用"}

        agent = self._agents["review"]
        task = {
            "content": content,
            "check_type": check_type,
            "standards": standards or ["enterprise", "safety"],
        }

        result = await agent.process(task, context)
        logger.info("review_only_completed", check_type=check_type)

        return result

    def get_interaction_status(self) -> Dict[str, Any]:
        """获取当前交互状态"""
        return {
            "is_awaiting_input": self.interaction_manager.is_awaiting_input(),
            "pending_interaction": self.interaction_manager.get_pending_interaction(),
            "current_state": self.state_machine.current_state.value,
            "collected_info_keys": list(self._collected_info.keys()),
        }

    # ============== 多轮迭代支持 ==============

    async def generate_with_iteration(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        task_name: Optional[str] = None,
        source_docs: Optional[List[str]] = None,
        user_feedback: Optional[UserFeedback] = None
    ) -> Dict[str, Any]:
        """
        带多轮迭代支持的内容生成

        流程：
        1. 首次生成内容
        2. 等待用户反馈
        3. 根据反馈进行增量修改（最多3轮）
        4. 返回最终结果

        Args:
            user_input: 用户输入
            context: 执行上下文
            task_name: 任务名称
            source_docs: 源文档列表
            user_feedback: 用户反馈（用于增量修改）

        Returns:
            生成结果
        """
        try:
            # 如果有用户反馈，处理反馈
            if user_feedback is not None:
                return await self._handle_iteration_feedback(user_feedback, context)

            # 重置迭代状态
            self._iteration_manager.reset()

            # 开始第一轮迭代
            iteration_num = self._iteration_manager.start_iteration()

            logger.info(
                "iteration_started",
                iteration=iteration_num,
                max_iterations=self._iteration_manager.max_iterations
            )

            # 执行首次生成
            result = await self.process_intent(
                user_input=user_input,
                context=context,
                task_name=task_name,
                source_docs=source_docs
            )

            if not result.get("success"):
                return result

            # 获取生成的内容
            generated_content = self._extract_generated_content(result)

            # 记录历史
            self._iteration_manager.record_history(
                content=generated_content,
                result=result
            )

            # 返回预览，等待用户反馈
            return {
                "success": True,
                "iteration": iteration_num,
                "status": "preview",
                "content": generated_content,
                "requires_feedback": True,
                "max_iterations": self._iteration_manager.max_iterations,
                "feedback_options": [
                    {"label": "确认通过", "value": "accept"},
                    {"label": "需要修改", "value": "modify"},
                    {"label": "取消", "value": "reject"}
                ]
            }

        except Exception as e:
            logger.error("generate_with_iteration_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "ITERATION_GENERATION_FAILED"
            }

    async def _handle_iteration_feedback(
        self,
        feedback: UserFeedback,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理迭代过程中的用户反馈

        Args:
            feedback: 用户反馈
            context: 执行上下文

        Returns:
            处理结果
        """
        iteration_result = self._iteration_manager.process_feedback(feedback)

        if iteration_result == IterationResult.COMPLETE:
            # User accepted — record iteration trail + trigger learning
            history = self._iteration_manager.get_history()
            logger.info(
                "iteration_completed",
                total_iterations=self._iteration_manager.current_iteration,
                iteration_history=history,
            )
            # Learning feedback: extract preferences from iteration diffs
            await self._learn_from_iteration(history)

            # 获取最后一轮的内容
            last_history = self._iteration_manager._history[-1] if self._iteration_manager._history else None

            return {
                "success": True,
                "status": "completed",
                "iteration": self._iteration_manager.current_iteration,
                "content": last_history.content if last_history else "",
                "history": self._iteration_manager.get_history()
            }

        elif iteration_result == IterationResult.MAX_REACHED:
            # 达到最大迭代次数
            logger.info(
                "iteration_max_reached",
                total_iterations=self._iteration_manager.current_iteration
            )

            last_history = self._iteration_manager._history[-1] if self._iteration_manager._history else None

            return {
                "success": True,
                "status": "max_iterations_reached",
                "iteration": self._iteration_manager.current_iteration,
                "content": last_history.content if last_history else "",
                "message": "已达到最大修改次数（3次）",
                "history": self._iteration_manager.get_history()
            }

        elif iteration_result == IterationResult.ABORT:
            # 用户中止
            logger.info("iteration_aborted")

            return {
                "success": True,
                "status": "aborted",
                "iteration": self._iteration_manager.current_iteration,
                "message": "用户已取消"
            }

        elif iteration_result == IterationResult.CONTINUE:
            # 继续迭代，进行增量修改
            new_iteration = self._iteration_manager.start_iteration()

            logger.info(
                "iteration_continue",
                iteration=new_iteration,
                feedback_content=feedback.content[:100] if feedback.content else ""
            )

            # 获取上一轮的内容
            last_history = self._iteration_manager._history[-1] if self._iteration_manager._history else None
            original_content = last_history.content if last_history else ""

            # 调用 Writing Agent 进行增量修改
            modified_result = await self._incremental_modify_content(
                original_content=original_content,
                feedback=feedback,
                context=context
            )

            if not modified_result.get("success"):
                return modified_result

            modified_content = modified_result.get("content", "")

            # 记录历史
            self._iteration_manager.record_history(
                content=modified_content,
                feedback=feedback,
                result=modified_result
            )

            # 返回新的预览
            return {
                "success": True,
                "iteration": new_iteration,
                "status": "preview",
                "content": modified_content,
                "requires_feedback": True,
                "max_iterations": self._iteration_manager.max_iterations,
                "feedback_options": [
                    {"label": "确认通过", "value": "accept"},
                    {"label": "继续修改", "value": "modify"},
                    {"label": "取消", "value": "reject"}
                ],
                "changes": modified_result.get("changes", [])
            }

        return {
            "success": False,
            "error": f"未知的迭代结果: {iteration_result}"
        }

    async def _incremental_modify_content(
        self,
        original_content: str,
        feedback: UserFeedback,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        增量修改内容

        Args:
            original_content: 原始内容
            feedback: 用户反馈
            context: 执行上下文

        Returns:
            修改结果
        """
        if "writing" not in self._agents:
            return {
                "success": False,
                "error": "Writing Agent 不可用"
            }

        writing_agent = self._agents["writing"]

        # 构建修改任务
        modify_task = {
            "action": "modify",
            "content": original_content,
            "feedback": {
                "type": feedback.type,
                "content": feedback.content,
                "suggestions": feedback.suggestions
            }
        }

        # 调用 Writing Agent 的 handle_feedback 方法
        if hasattr(writing_agent, 'handle_feedback'):
            from app.agents.functional.writing_agent import UserFeedback as WritingFeedback, FeedbackType

            # 转换反馈类型
            feedback_type = FeedbackType.MODIFY
            if feedback.type == "accept":
                feedback_type = FeedbackType.ACCEPT
            elif feedback.type == "reject":
                feedback_type = FeedbackType.REJECT

            writing_feedback = WritingFeedback(
                type=feedback_type,
                content=feedback.content,
                suggestions=feedback.suggestions
            )

            result = await writing_agent.handle_feedback(writing_feedback, modify_task)
        else:
            # 回退到普通的 process 方法
            result = await writing_agent.process(modify_task, context)

        logger.info(
            "incremental_modify_completed",
            success=result.get("success"),
            has_content=bool(result.get("content"))
        )

        return result

    def _extract_generated_content(self, result: Dict[str, Any]) -> str:
        """
        从处理结果中提取生成的内容

        Args:
            result: 处理结果

        Returns:
            提取的内容
        """
        # 尝试从不同的位置提取内容
        if "result" in result:
            inner_result = result["result"]
            if isinstance(inner_result, dict):
                if "generated_content" in inner_result:
                    return inner_result["generated_content"]
                if "content" in inner_result:
                    return inner_result["content"]

        if "generated_content" in result:
            return result["generated_content"]

        if "content" in result:
            return result["content"]

        return ""

    def get_iteration_status(self) -> Dict[str, Any]:
        """
        获取迭代状态

        Returns:
            迭代状态信息
        """
        return {
            "current_iteration": self._iteration_manager.current_iteration,
            "max_iterations": self._iteration_manager.max_iterations,
            "can_continue": self._iteration_manager.can_continue,
            "history_count": len(self._iteration_manager._history)
        }

    # ============== Learning Feedback Loop ==============

    async def _learn_from_iteration(self, history: List[Dict[str, Any]]) -> None:
        """Extract writing preferences from iteration diffs and update profile.

        This implements the Hermes-style Learning loop:
        1. Compare initial content with final accepted content
        2. Extract structural/lexical differences
        3. Convert differences into Preference entries
        4. Write back to the domain profile

        Args:
            history: iteration history from IterationManager
        """
        if len(history) < 2:
            return

        try:
            initial_content = history[0].get("content", "")
            final_content = history[-1].get("content", "")

            if not initial_content or not final_content:
                return

            # Extract diffs
            preferences = self._extract_prefs_from_diff(initial_content, final_content)
            if not preferences:
                return

            # Write to profile
            domain = self.config.get("domain", "assembly")
            self._update_profile_preferences(domain, preferences)

            logger.info(
                "learning_feedback_applied",
                domain=domain,
                new_preference_count=len(preferences),
            )

        except Exception as e:
            logger.warning("learning_feedback_failed", error=str(e))

    def _extract_prefs_from_diff(
        self, initial: str, final: str
    ) -> List[Dict[str, Any]]:
        """Extract preference entries from content diff.

        Uses rule-based diff analysis (no LLM call needed):
        - Sentence length changes → sentence_structure preference
        - Added caution notes → caution_note preference
        - Terminology changes → vocabulary preference
        """
        import re as _re
        from app.models.profile import Preference

        prefs: List[Dict[str, Any]] = []

        # Diff 1: Sentence length
        init_sentences = [s.strip() for s in _re.split(r"[。！？\n]+", initial) if s.strip()]
        final_sentences = [s.strip() for s in _re.split(r"[。！？\n]+", final) if s.strip()]
        if init_sentences and final_sentences:
            init_avg = sum(len(s) for s in init_sentences) / len(init_sentences)
            final_avg = sum(len(s) for s in final_sentences) / len(final_sentences)
            if abs(final_avg - init_avg) > 8:
                direction = "短句" if final_avg < init_avg else "长句"
                prefs.append(Preference(
                    dimension="style",
                    category="sentence_structure",
                    description=f"用户偏好{direction}表述（平均句长从{init_avg:.0f}字调整为{final_avg:.0f}字）",
                    learned_from="user_correction",
                    sample_count=1,
                    confidence=0.3,
                ).to_dict())

        # Diff 2: Caution notes added
        init_caution = len(_re.findall(r"注意|警告|安全|危险|禁止|严禁", initial))
        final_caution = len(_re.findall(r"注意|警告|安全|危险|禁止|严禁", final))
        if final_caution > init_caution + 1:
            prefs.append(Preference(
                dimension="style",
                category="caution_notes",
                description="用户倾向在关键工序后添加安全注意事项",
                positive_examples=["注意：操作前确认力矩", "警告：高温作业须佩戴防护手套"],
                learned_from="user_correction",
                sample_count=1,
                confidence=0.4,
            ).to_dict())

        # Diff 3: Terminology changes (word-level diff)
        init_terms = set(_re.findall(r"[\u4e00-\u9fff]{2,6}", initial))
        final_terms = set(_re.findall(r"[\u4e00-\u9fff]{2,6}", final))
        new_terms = final_terms - init_terms
        removed_terms = init_terms - final_terms
        if new_terms and removed_terms:
            # Find potential terminology replacements
            vocab = {}
            for nt in list(new_terms)[:5]:
                for rt in list(removed_terms)[:5]:
                    if abs(len(nt) - len(rt)) <= 1:
                        vocab[rt] = nt
                        break
            if vocab:
                prefs.append(Preference(
                    dimension="style",
                    category="vocabulary",
                    description="用户偏好特定术语表达",
                    positive_examples=list(vocab.values()),
                    negative_examples=list(vocab.keys()),
                    learned_from="user_correction",
                    sample_count=1,
                    confidence=0.3,
                ).to_dict())

        return prefs

    def _update_profile_preferences(
        self, domain: str, new_prefs: List[Dict[str, Any]]
    ) -> None:
        """Write learned preferences to domain profile file."""
        try:
            from app.models.profile import Profile, Preference
            from app.config import settings
            from pathlib import Path

            profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"
            profile_path.parent.mkdir(parents=True, exist_ok=True)

            if profile_path.exists():
                profile = Profile.from_json(profile_path)
            else:
                from app.models.profile import get_default_assembly_profile
                profile = get_default_assembly_profile()

            for pref_dict in new_prefs:
                pref = Preference.from_dict(pref_dict)
                profile.add_preference(pref)

            profile.to_json(profile_path)
            logger.info(
                "profile_preferences_updated",
                domain=domain,
                total_preferences=len(profile.preferences_list),
            )
        except Exception as e:
            logger.warning("profile_update_failed", domain=domain, error=str(e))
