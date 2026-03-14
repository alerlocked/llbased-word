"""
工艺文件辅助编辑系统 - 主控Agent (ProcessOrchestrator)
负责协调整个工艺文件编辑流程，管理子Agent调度和会话状态

集成任务记忆系统和上下文管理
使用新的三层架构：Orchestrator -> 功能Agent -> Tool

交互流程：
1. 意图识别 → 2. 信息完整性评估 → 3. 信息收集(如需) → 4. 预览生成 → 5. 用户确认 → 6. 任务执行
"""
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import asyncio

from app.shared.logging import get_logger
from .state_machine import ProcessStateMachine, ProcessState
from .dialog_manager import DialogManager
from .intent_recognizer import IntentRecognizer
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

        logger.info(
            "process_orchestrator_initialized",
            config_keys=list(self.config.keys()),
            has_repository=repository is not None,
            has_context_builder=context_builder is not None,
            available_agents=list(self._agents.keys()),
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

            # 2. 构建上下文
            full_context = await self._build_context(context)

            # 3. 更新会话状态
            await self.state_machine.transition_to(
                ProcessState.INTENT_RECOGNITION,
                context_update={"user_input": user_input},
                trigger="process_intent",
            )

            # 4. 识别意图
            intent = await self.intent_recognizer.recognize(user_input, full_context)
            logger.info("intent_recognized", intent_type=intent.get("type"), confidence=intent.get("confidence"))

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
                    "action": task_type,
                    "content": task.get("content", ""),
                    "target": task.get("target"),
                    "requirements": task.get("requirements"),
                    **task.get("params", {})
                }

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
        执行指定工作流

        Args:
            workflow_name: 工作流名称
            task: 任务描述
            context: 执行上下文

        Returns:
            工作流执行结果
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return {
                "success": False,
                "error": f"工作流不存在: {workflow_name}"
            }

        results = []
        current_content = task.get("content", "")

        for agent_name in workflow:
            if agent_name not in self._agents:
                logger.warning("agent_not_in_workflow", agent=agent_name)
                continue

            agent = self._agents[agent_name]

            # 构建Agent任务
            agent_task = {
                "content": current_content,
                **task
            }

            # 执行Agent
            result = await agent.process(agent_task, context)
            results.append({
                "agent": agent_name,
                "result": result
            })

            # 更新内容（如果Agent修改了内容）
            if result.get("success") and result.get("result", {}).get("content"):
                current_content = result["result"]["content"]

            # 如果是审查Agent且未通过，记录问题
            if agent_name == "review" and not result.get("result", {}).get("passed"):
                logger.warning(
                    "workflow_review_failed",
                    issues=result.get("result", {}).get("warnings", [])
                )

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

    async def _handle_user_response(self, response: UserResponse) -> Dict[str, Any]:
        """处理用户响应"""
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
