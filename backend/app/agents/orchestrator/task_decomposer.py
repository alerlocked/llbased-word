"""
工艺文件辅助编辑系统 - 任务分解器
将识别出的工艺意图分解为具体的可执行子任务
"""
from typing import Dict, Any, List, Optional
from enum import Enum

from app.shared.logging import get_logger
from .intent_recognizer import IntentType

logger = get_logger(__name__)


class TaskType(Enum):
    """任务类型枚举"""
    PDF_PARSING = "pdf_parsing"              # PDF解析任务
    RAG_RETRIEVAL = "rag_retrieval"          # RAG检索任务
    TERMINOLOGY_ALIGNMENT = "terminology_alignment"  # 术语对齐任务
    COMPLIANCE_CHECK = "compliance_check"    # 合规检查任务
    DOCUMENT_GENERATION = "document_generation"  # 文档生成任务
    DATA_VALIDATION = "data_validation"      # 数据验证任务
    USER_CONFIRMATION = "user_confirmation"  # 用户确认任务
    ERROR_HANDLING = "error_handling"        # 错误处理任务


class TaskDecomposer:
    """
    任务分解器

    将识别出的工艺意图分解为一系列具体的子任务，
    每个子任务可以由相应的子Agent或工具模块执行
    """

    # 意图到任务的映射规则
    INTENT_TO_TASKS = {
        IntentType.CREATE_DOCUMENT: [
            TaskType.RAG_RETRIEVAL,      # 检索相关工艺知识
            TaskType.TERMINOLOGY_ALIGNMENT,  # 对齐工艺术语
            TaskType.DOCUMENT_GENERATION,  # 生成工艺文档
            TaskType.COMPLIANCE_CHECK,   # 检查合规性
            TaskType.USER_CONFIRMATION   # 用户确认
        ],
        IntentType.EDIT_DOCUMENT: [
            TaskType.PDF_PARSING,        # 解析现有文档（如果是PDF）
            TaskType.DATA_VALIDATION,    # 验证编辑内容
            TaskType.COMPLIANCE_CHECK,   # 检查编辑后的合规性
            TaskType.USER_CONFIRMATION   # 用户确认
        ],
        IntentType.REVIEW_DOCUMENT: [
            TaskType.COMPLIANCE_CHECK,   # 详细合规检查
            TaskType.DATA_VALIDATION,    # 数据完整性验证
            TaskType.USER_CONFIRMATION   # 审核确认
        ],
        IntentType.GENERATE_DOCUMENT: [
            TaskType.DOCUMENT_GENERATION,  # 生成输出文件
            TaskType.USER_CONFIRMATION   # 用户确认生成结果
        ],
        IntentType.PARSE_PDF: [
            TaskType.PDF_PARSING,        # PDF解析
            TaskType.DATA_VALIDATION,    # 验证解析结果
            TaskType.USER_CONFIRMATION   # 用户确认解析结果
        ],
        IntentType.SEARCH_KNOWLEDGE: [
            TaskType.RAG_RETRIEVAL,      # 知识检索
            TaskType.USER_CONFIRMATION   # 用户确认检索结果
        ],
        IntentType.ALIGN_TERMINOLOGY: [
            TaskType.TERMINOLOGY_ALIGNMENT,  # 术语对齐
            TaskType.USER_CONFIRMATION   # 用户确认对齐结果
        ],
        IntentType.CHECK_COMPLIANCE: [
            TaskType.COMPLIANCE_CHECK,   # 合规检查
            TaskType.USER_CONFIRMATION   # 用户确认检查结果
        ],
        IntentType.EXPORT_TO_PDM: [
            TaskType.DOCUMENT_GENERATION,  # 生成导出格式
            TaskType.DATA_VALIDATION,    # 验证导出数据
            TaskType.USER_CONFIRMATION   # 用户确认导出
        ]
    }

    def __init__(self):
        """初始化任务分解器"""
        logger.info("task_decomposer_initialized")

    async def decompose(self, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将意图分解为任务列表

        Args:
            intent: 意图识别结果

        Returns:
            任务列表，每个任务包含类型、参数和依赖关系
        """
        try:
            intent_type_str = intent.get("type")
            intent_type = IntentType(intent_type_str) if intent_type_str else IntentType.UNKNOWN

            # 获取基础任务序列
            base_tasks = self.INTENT_TO_TASKS.get(intent_type, [])

            # 根据意图详情和实体调整任务
            tasks = self._customize_tasks(base_tasks, intent)

            # 添加任务依赖关系
            tasks_with_deps = self._add_dependencies(tasks)

            # 添加任务参数
            final_tasks = self._add_task_parameters(tasks_with_deps, intent)

            logger.info(
                "tasks_decomposed",
                intent_type=intent_type.value,
                task_count=len(final_tasks),
                task_types=[t["type"] for t in final_tasks]
            )

            return final_tasks

        except Exception as e:
            logger.error("task_decomposition_failed", error=str(e), intent=intent)
            # 返回一个基本的错误处理任务
            return [self._create_error_task(str(e))]

    def _customize_tasks(self, base_tasks: List[TaskType], intent: Dict[str, Any]) -> List[TaskType]:
        """
        根据意图详情定制任务序列

        Args:
            base_tasks: 基础任务序列
            intent: 意图详情

        Returns:
            定制后的任务序列
        """
        customized_tasks = base_tasks.copy()
        entities = intent.get("entities", {})
        confidence = intent.get("confidence", 0)

        # 根据提取的实体调整任务
        if "operation" in entities and len(entities["operation"]) > 0:
            # 如果提到了工序，可能需要更详细的数据验证
            if TaskType.DATA_VALIDATION not in customized_tasks:
                customized_tasks.insert(1, TaskType.DATA_VALIDATION)

        if "parameter" in entities and len(entities["parameter"]) > 0:
            # 如果提到了参数，可能需要参数验证
            pass

        # 根据置信度调整任务
        if confidence < 0.5:
            # 低置信度时添加额外的用户确认
            if TaskType.USER_CONFIRMATION not in customized_tasks:
                customized_tasks.append(TaskType.USER_CONFIRMATION)

        return customized_tasks

    def _add_dependencies(self, tasks: List[TaskType]) -> List[Dict[str, Any]]:
        """
        添加任务依赖关系

        Args:
            tasks: 任务类型列表

        Returns:
            带有依赖关系的任务字典列表
        """
        tasks_with_deps = []

        for i, task_type in enumerate(tasks):
            task_dict = {
                "id": f"task_{i+1}",
                "type": task_type.value,
                "name": self._get_task_name(task_type),
                "description": self._get_task_description(task_type),
                "dependencies": [],  # 默认无依赖
                "estimated_duration": self._get_estimated_duration(task_type),
                "priority": self._get_task_priority(task_type, i, len(tasks))
            }

            # 添加简单的前置依赖（前一个任务）
            if i > 0:
                task_dict["dependencies"] = [f"task_{i}"]

            tasks_with_deps.append(task_dict)

        return tasks_with_deps

    def _add_task_parameters(self, tasks: List[Dict[str, Any]], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        为任务添加具体参数

        Args:
            tasks: 任务列表（带依赖）
            intent: 意图详情

        Returns:
            带有参数的任务列表
        """
        for task in tasks:
            task_type = TaskType(task["type"])
            task["parameters"] = self._get_task_parameters(task_type, intent)

            # 添加执行条件
            task["conditions"] = self._get_execution_conditions(task_type)

            # 添加预期输出
            task["expected_output"] = self._get_expected_output(task_type)

        return tasks

    def _get_task_name(self, task_type: TaskType) -> str:
        """获取任务名称"""
        names = {
            TaskType.PDF_PARSING: "PDF文档解析",
            TaskType.RAG_RETRIEVAL: "工艺知识检索",
            TaskType.TERMINOLOGY_ALIGNMENT: "工艺术语对齐",
            TaskType.COMPLIANCE_CHECK: "合规性检查",
            TaskType.DOCUMENT_GENERATION: "工艺文档生成",
            TaskType.DATA_VALIDATION: "数据验证",
            TaskType.USER_CONFIRMATION: "用户确认",
            TaskType.ERROR_HANDLING: "错误处理"
        }
        return names.get(task_type, "未知任务")

    def _get_task_description(self, task_type: TaskType) -> str:
        """获取任务描述"""
        descriptions = {
            TaskType.PDF_PARSING: "解析PDF格式的工艺文件，提取表格、文本和结构信息",
            TaskType.RAG_RETRIEVAL: "从工艺知识库中检索相关的工艺标准、案例和规范",
            TaskType.TERMINOLOGY_ALIGNMENT: "将用户描述转换为标准的工艺术语和表达",
            TaskType.COMPLIANCE_CHECK: "检查工艺文件是否符合企业标准和行业规范",
            TaskType.DOCUMENT_GENERATION: "生成标准格式的工艺文件（PDF、Word等）",
            TaskType.DATA_VALIDATION: "验证工艺数据的完整性和正确性",
            TaskType.USER_CONFIRMATION: "获取用户对中间结果或最终结果的确认",
            TaskType.ERROR_HANDLING: "处理执行过程中出现的错误和异常"
        }
        return descriptions.get(task_type, "未知任务描述")

    def _get_estimated_duration(self, task_type: TaskType) -> int:
        """获取预估执行时间（秒）"""
        durations = {
            TaskType.PDF_PARSING: 30,
            TaskType.RAG_RETRIEVAL: 10,
            TaskType.TERMINOLOGY_ALIGNMENT: 15,
            TaskType.COMPLIANCE_CHECK: 20,
            TaskType.DOCUMENT_GENERATION: 25,
            TaskType.DATA_VALIDATION: 10,
            TaskType.USER_CONFIRMATION: 5,  # 等待用户响应的时间
            TaskType.ERROR_HANDLING: 10
        }
        return durations.get(task_type, 15)

    def _get_task_priority(self, task_type: TaskType, index: int, total: int) -> str:
        """获取任务优先级"""
        # 用户确认任务通常是最后执行
        if task_type == TaskType.USER_CONFIRMATION:
            return "low"

        # 错误处理任务优先级较高
        if task_type == TaskType.ERROR_HANDLING:
            return "high"

        # 前面的任务优先级较高
        if index < total / 3:
            return "high"
        elif index < 2 * total / 3:
            return "medium"
        else:
            return "low"

    def _get_task_parameters(self, task_type: TaskType, intent: Dict[str, Any]) -> Dict[str, Any]:
        """获取任务参数"""
        base_params = {
            "intent_type": intent.get("type"),
            "confidence": intent.get("confidence", 0),
            "entities": intent.get("entities", {}),
            "original_input": intent.get("original_input", "")
        }

        # 任务特定参数
        specific_params = {}

        if task_type == TaskType.PDF_PARSING:
            specific_params = {
                "extract_tables": True,
                "extract_text": True,
                "identify_structure": True,
                "accuracy_threshold": 0.97  # 97%准确性要求
            }

        elif task_type == TaskType.RAG_RETRIEVAL:
            specific_params = {
                "search_query": intent.get("original_input", ""),
                "top_k": 5,
                "rerank": True,
                "use_cache": True
            }

        elif task_type == TaskType.TERMINOLOGY_ALIGNMENT:
            specific_params = {
                "source_terms": list(intent.get("entities", {}).keys()),
                "target_standard": "企业工艺术语标准",
                "allow_suggestions": True
            }

        elif task_type == TaskType.COMPLIANCE_CHECK:
            specific_params = {
                "check_level": "detailed",
                "include_standards": ["企业标准", "行业规范", "安全要求"],
                "generate_report": True
            }

        elif task_type == TaskType.DOCUMENT_GENERATION:
            specific_params = {
                "output_formats": ["pdf", "word"],
                "template": "standard_process_template",
                "include_metadata": True
            }

        elif task_type == TaskType.USER_CONFIRMATION:
            specific_params = {
                "timeout_seconds": 300,  # 5分钟超时
                "allow_skip": False,
                "confirmation_type": "intermediate" if task_type != TaskType.USER_CONFIRMATION else "final"
            }

        base_params.update(specific_params)
        return base_params

    def _get_execution_conditions(self, task_type: TaskType) -> Dict[str, Any]:
        """获取执行条件"""
        conditions = {
            "preconditions": [],
            "postconditions": [],
            "failure_handling": "retry_then_fallback"
        }

        if task_type == TaskType.PDF_PARSING:
            conditions["preconditions"] = [
                "PDF文件存在且可访问",
                "文件大小不超过100MB"
            ]
            conditions["failure_handling"] = "fallback_to_manual"

        elif task_type == TaskType.USER_CONFIRMATION:
            conditions["preconditions"] = [
                "前序任务已完成",
                "用户在线且可交互"
            ]
            conditions["failure_handling"] = "wait_and_retry"

        return conditions

    def _get_expected_output(self, task_type: TaskType) -> Dict[str, Any]:
        """获取预期输出"""
        outputs = {
            TaskType.PDF_PARSING: {
                "format": "json",
                "content": ["tables", "text", "structure"],
                "accuracy": "≥97%"
            },
            TaskType.RAG_RETRIEVAL: {
                "format": "list",
                "content": ["relevant_documents", "scores", "snippets"],
                "count": "top_5"
            },
            TaskType.TERMINOLOGY_ALIGNMENT: {
                "format": "mapping",
                "content": ["standard_terms", "confidence_scores", "alternatives"],
                "coverage": "≥95%"
            },
            TaskType.COMPLIANCE_CHECK: {
                "format": "report",
                "content": ["issues", "suggestions", "compliance_score"],
                "detail_level": "detailed"
            },
            TaskType.DOCUMENT_GENERATION: {
                "format": "file",
                "content": ["generated_files", "metadata", "preview_url"],
                "quality": "production_ready"
            },
            TaskType.USER_CONFIRMATION: {
                "format": "confirmation",
                "content": ["user_response", "timestamp", "feedback"],
                "required": True
            }
        }

        return outputs.get(task_type, {"format": "unknown", "content": []})

    def _create_error_task(self, error_message: str) -> Dict[str, Any]:
        """创建错误处理任务"""
        return {
            "id": "task_error",
            "type": TaskType.ERROR_HANDLING.value,
            "name": "错误处理",
            "description": f"处理任务分解过程中的错误: {error_message}",
            "dependencies": [],
            "estimated_duration": 10,
            "priority": "high",
            "parameters": {
                "error_message": error_message,
                "recovery_strategy": "fallback_to_manual"
            },
            "conditions": {
                "preconditions": ["错误发生"],
                "postconditions": ["错误已处理或上报"],
                "failure_handling": "notify_administrator"
            },
            "expected_output": {
                "format": "error_report",
                "content": ["error_details", "recovery_attempts", "final_status"]
            }
        }

    async def adjust_tasks_based_on_feedback(
        self,
        current_tasks: List[Dict[str, Any]],
        feedback: Dict[str, Any],
        execution_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        根据执行反馈调整任务

        Args:
            current_tasks: 当前任务列表
            feedback: 用户或系统反馈
            execution_results: 已执行任务的结果

        Returns:
            调整后的任务列表
        """
        adjusted_tasks = current_tasks.copy()

        # 分析反馈类型
        feedback_type = feedback.get("type")

        if feedback_type == "skip_task":
            # 跳过特定任务
            task_id_to_skip = feedback.get("task_id")
            adjusted_tasks = [t for t in adjusted_tasks if t["id"] != task_id_to_skip]

        elif feedback_type == "add_task":
            # 添加新任务
            new_task_type = feedback.get("task_type")
            if new_task_type:
                try:
                    task_type = TaskType(new_task_type)
                    new_task = self._create_custom_task(task_type, feedback)
                    adjusted_tasks.append(new_task)
                except ValueError:
                    logger.warning("invalid_task_type_in_feedback", task_type=new_task_type)

        elif feedback_type == "reorder_tasks":
            # 重新排序任务
            new_order = feedback.get("new_order", [])
            if new_order:
                # 根据新顺序重新排列任务
                task_dict = {t["id"]: t for t in adjusted_tasks}
                adjusted_tasks = [task_dict.get(task_id) for task_id in new_order if task_id in task_dict]

        elif feedback_type == "change_parameters":
            # 修改任务参数
            task_id = feedback.get("task_id")
            new_params = feedback.get("parameters", {})
            for task in adjusted_tasks:
                if task["id"] == task_id:
                    task["parameters"].update(new_params)
                    break

        logger.info(
            "tasks_adjusted_based_on_feedback",
            feedback_type=feedback_type,
            original_count=len(current_tasks),
            adjusted_count=len(adjusted_tasks)
        )

        return adjusted_tasks

    def _create_custom_task(self, task_type: TaskType, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """创建自定义任务"""
        return {
            "id": f"task_custom_{len(feedback)}",
            "type": task_type.value,
            "name": feedback.get("task_name", self._get_task_name(task_type)),
            "description": feedback.get("task_description", self._get_task_description(task_type)),
            "dependencies": feedback.get("dependencies", []),
            "estimated_duration": feedback.get("estimated_duration", self._get_estimated_duration(task_type)),
            "priority": feedback.get("priority", "medium"),
            "parameters": feedback.get("parameters", {}),
            "conditions": feedback.get("conditions", self._get_execution_conditions(task_type)),
            "expected_output": feedback.get("expected_output", self._get_expected_output(task_type))
        }