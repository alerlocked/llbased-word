"""
用户交互管理器

管理与用户的交互流程
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.shared.logging import get_logger
from app.agents.orchestrator.interaction_models import (
    InteractionType,
    InputType,
    InfoRequestMessage,
    PreviewMessage,
    ConfirmationMessage,
    ProgressMessage,
    ResultMessage,
    ErrorMessage,
    MissingInfoItem,
    UserResponse,
    InteractionMessage
)

logger = get_logger(__name__)


class InteractionManager:
    """
    用户交互管理器

    管理与用户的交互流程，    - 生成信息请求消息
    - 生成预览消息
    - 处理用户响应
    """

    def __init__(
        self,
        repository=None,
        dialog_manager=None
    ):
        """
        初始化交互管理器

        Args:
            repository: 任务记忆仓库
            dialog_manager: 对话管理器
        """
        self.repository = repository
        self.dialog_manager = dialog_manager

        # 当前待处理的交互
        self._pending_interaction: Optional[Dict[str, Any]] = None

        # 会话信息缓存
        self._session_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("interaction_manager_initialized")

    async def request_missing_info(
        self,
        missing_info: Dict[str, List],
        context: Dict[str, Any]
    ) -> InfoRequestMessage:
        """
        生成信息请求消息

        Args:
            missing_info: 缺失信息（按优先级分组）
            context: 当前上下文

        Returns:
            信息请求消息
        """
        # 转换为MissingInfoItem列表
        missing_items = []

        # 高优先级
        for item in missing_info.get("high_priority", []):
            if isinstance(item, dict):
                missing_items.append(MissingInfoItem(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    example=item.get("example"),
                    impact=item.get("impact", "必须提供"),
                    priority="high",
                    input_type=item.get("input_type", "text")
                ))

        # 中优先级
        for item in missing_info.get("medium_priority", []):
            if isinstance(item, dict):
                missing_items.append(MissingInfoItem(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    example=item.get("example"),
                    impact=item.get("impact", "影响结果质量"),
                    priority="medium",
                    input_type=item.get("input_type", "text")
                ))

        # 低优先级
        for item in missing_info.get("low_priority", []):
            if isinstance(item, dict):
                missing_items.append(MissingInfoItem(
                    name=item.get("name", ""),
                    description=item.get("description", ""),
                    example=item.get("example"),
                    impact=item.get("impact", "可使用默认值"),
                    priority="low",
                    input_type=item.get("input_type", "text")
                ))

        # 生成消息
        high_count = len(missing_info.get("high_priority", []))
        medium_count = len(missing_info.get("medium_priority", []))

        if high_count > 0 and medium_count > 0:
            message = f"检测到 {high_count} 项高优先级、{medium_count} 项中优先级信息缺失，需要您确认："
        elif high_count > 0:
            message = f"检测到 {high_count} 项高优先级信息缺失，需要您确认："
        elif medium_count > 0:
            message = f"检测到 {medium_count} 项中优先级信息缺失，建议您补充："
        else:
            message = "需要您确认一些信息："

        # 生成建议
        suggestions = [
            "直接回复补充信息",
            "上传相关图纸或文档",
        ]
        if missing_info.get("can_skip"):
            suggestions.append("跳过使用默认值（可能影响结果精度）")

        # 记录待处理交互
        self._pending_interaction = {
            "type": InteractionType.INFO_REQUEST,
            "missing_items": [item.model_dump() for item in missing_items],
            "created_at": datetime.now().isoformat()
        }

        logger.info(
            "info_request_generated",
            high_count=high_count,
            medium_count=medium_count,
            can_skip=missing_info.get("can_skip", False)
        )

        return InfoRequestMessage(
            message=message,
            missing_items=missing_items,
            suggestions=suggestions
        )

    async def generate_preview(
        self,
        intent: Dict[str, Any],
        collected_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> PreviewMessage:
        """
        生成预览消息

        Args:
            intent: 意图识别结果
            collected_info: 已收集的信息
            context: 当前上下文

        Returns:
            预览消息
        """
        # 根据意图类型确定处理方向
        intent_type = intent.get("type", "unknown")
        direction = self._generate_direction(intent_type, collected_info)
        expected_result = self._generate_expected_result(intent_type, collected_info)

        # 记录待处理交互
        self._pending_interaction = {
            "type": InteractionType.PREVIEW,
            "intent": intent,
            "collected_info": collected_info,
            "created_at": datetime.now().isoformat()
        }

        logger.info(
            "preview_generated",
            intent_type=intent_type,
            direction=direction
        )

        return PreviewMessage(
            direction=direction,
            expected_result=expected_result
        )

    def _generate_direction(
        self,
        intent_type: str,
        collected_info: Dict[str, Any]
    ) -> str:
        """生成处理方向描述"""
        # 方向模板
        templates = {
            "create": "将创建新的{doc_type}工艺文件",
            "edit": "将编辑{target}部分的内容",
            "calculate": "将计算{calc_type}相关参数",
            "proofread": "将对内容进行{check_type}检查",
            "review": "将进行{review_type}审查",
            "unknown": "将处理您的请求"
        }

        template = templates.get(intent_type, templates["unknown"])

        # 填充参数
        params = {
            "doc_type": collected_info.get("document_type", "工艺"),
            "target": collected_info.get("target_section", "指定"),
            "calc_type": collected_info.get("calculation_type", ""),
            "check_type": collected_info.get("check_type", "全面"),
            "review_type": collected_info.get("review_type", "合规")
        }

        try:
            return template.format(**params)
        except KeyError:
            return template

    def _generate_expected_result(
        self,
        intent_type: str,
        collected_info: Dict[str, Any]
    ) -> str:
        """生成预期结果描述"""
        # 结果模板
        templates = {
            "create": "输出完整的工艺文件内容",
            "edit": "输出修改后的内容，包含变更说明",
            "calculate": "输出计算结果和推荐参数值",
            "proofread": "输出校对结果、问题列表和修改建议",
            "review": "输出审查报告，包含合规状态和风险提示",
            "unknown": "输出处理结果"
        }

        return templates.get(intent_type, templates["unknown"])

    async def generate_confirmation(
        self,
        message: str,
        options: List[Dict[str, str]]
    ) -> ConfirmationMessage:
        """
        生成确认消息

        Args:
            message: 确认消息
            options: 选项列表

        Returns:
            确认消息
        """
        # 默认选项
        if not options:
            options = [
                {"label": "确认执行", "value": "confirm"},
                {"label": "需要修改", "value": "modify"},
                {"label": "取消", "value": "cancel"}
            ]

        self._pending_interaction = {
            "type": InteractionType.CONFIRMATION,
            "options": options,
            "created_at": datetime.now().isoformat()
        }

        logger.info("confirmation_generated", options_count=len(options))

        return ConfirmationMessage(
            message=message,
            options=options
        )

    async def process_user_response(
        self,
        response: UserResponse
    ) -> Dict[str, Any]:
        """
        处理用户响应

        Args:
            response: 用户响应

        Returns:
            处理结果
        """
        if not self._pending_interaction:
            return {
                "success": False,
                "error": "没有待处理的交互"
            }

        pending_type = self._pending_interaction.get("type")

        result = {
            "success": True,
            "response_type": response.response_type.value,
            "pending_type": pending_type.value if hasattr(pending_type, 'value') else pending_type
        }

        # 根据待处理类型处理响应
        if pending_type == InteractionType.INFO_REQUEST:
            # 处理信息补充
            result["collected_info"] = self._extract_info_from_response(response)
            result["action"] = "continue_assessment"

        elif pending_type == InteractionType.PREVIEW:
            # 处理预览确认
            if response.selected_option == "confirm":
                result["action"] = "start_execution"
            elif response.selected_option == "modify":
                result["action"] = "request_modification"
            else:
                result["action"] = "cancel"

        elif pending_type == InteractionType.CONFIRMATION:
            # 处理确认响应
            result["action"] = "execute" if response.selected_option == "confirm" else "cancel"

        # 清除待处理交互
        self._pending_interaction = None

        logger.info(
            "user_response_processed",
            response_type=response.response_type.value,
            action=result.get("action")
        )

        return result

    def _extract_info_from_response(self, response: UserResponse) -> Dict[str, Any]:
        """从用户响应中提取信息"""
        info = {}

        if response.response_type == InputType.TEXT:
            # 文字响应，尝试解析
            if isinstance(response.content, str):
                # 简单的键值对解析（格式：key=value 或 key: value）
                content = response.content
                for part in content.split(","):
                    if "=" in part:
                        key, value = part.split("=", 1)
                        info[key.strip()] = value.strip()
                    elif ":" in part:
                        key, value = part.split(":", 1)
                        info[key.strip()] = value.strip()

                # 如果没有键值对，整个内容作为一个值
                if not info:
                    info["user_input"] = content

        elif response.response_type == InputType.FILE:
            # 文件响应
            if isinstance(response.content, list):
                info["uploaded_files"] = response.content
            else:
                info["uploaded_files"] = [response.content]

        elif response.response_type == InputType.IMAGE:
            # 图片响应
            if isinstance(response.content, list):
                info["uploaded_images"] = response.content
            else:
                info["uploaded_images"] = [response.content]

        # 合并附加信息
        if response.additional_info:
            info.update(response.additional_info)

        return info

    def is_awaiting_input(self) -> bool:
        """是否在等待用户输入"""
        return self._pending_interaction is not None

    def get_pending_interaction(self) -> Optional[Dict[str, Any]]:
        """获取待处理的交互"""
        return self._pending_interaction

    def clear_pending_interaction(self):
        """清除待处理的交互"""
        self._pending_interaction = None
        logger.info("pending_interaction_cleared")

    async def generate_progress_message(
        self,
        current_step: str,
        total_steps: int,
        completed_steps: int,
        message: Optional[str] = None
    ) -> ProgressMessage:
        """生成进度消息"""
        return ProgressMessage(
            current_step=current_step,
            total_steps=total_steps,
            completed_steps=completed_steps,
            message=message
        )

    async def generate_result_message(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ) -> ResultMessage:
        """生成结果消息"""
        return ResultMessage(
            success=success,
            message=message,
            data=data,
            suggestions=suggestions or []
        )

    async def generate_error_message(
        self,
        error_code: str,
        error_message: str,
        suggestions: Optional[List[str]] = None,
        can_retry: bool = True
    ) -> ErrorMessage:
        """生成错误消息"""
        return ErrorMessage(
            error_code=error_code,
            error_message=error_message,
            suggestions=suggestions or [],
            can_retry=can_retry
        )
