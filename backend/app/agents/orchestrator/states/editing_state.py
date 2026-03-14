"""
工艺文件辅助编辑系统 - 编辑状态
处理工艺文件的编辑和修改操作
"""
from typing import Dict, Any, Optional
from datetime import datetime

from .base_state import BaseState, StateType
from app.shared.logging import get_logger

logger = get_logger(__name__)


class EditingState(BaseState):
    """
    编辑状态

    处理工艺文件的编辑操作，包括：
    1. 接收用户编辑指令
    2. 应用编辑操作
    3. 验证编辑结果
    4. 准备进入审核状态
    """

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """初始化编辑状态"""
        super().__init__(StateType.EDITING, context)
        self.edit_history = []
        self.current_document = None

    async def on_enter(self, previous_state: Optional[BaseState] = None):
        """
        进入编辑状态

        Args:
            previous_state: 前一个状态
        """
        self.entered_at = datetime.now().isoformat()

        # 初始化编辑上下文
        if "document" in self.context:
            self.current_document = self.context["document"]
            logger.info("editing_state_entered", document_id=self.current_document.get("id", "unknown"))
        else:
            logger.warning("editing_state_entered_without_document")

        # 记录状态转换
        previous_type = previous_state.state_type.value if previous_state else "none"
        self._log_state_transition("enter", previous_state)

    async def on_exit(self, next_state: Optional[BaseState] = None):
        """
        退出编辑状态

        Args:
            next_state: 下一个状态
        """
        self.exited_at = datetime.now().isoformat()

        # 保存编辑历史到上下文
        if self.edit_history:
            self.context["edit_history"] = self.edit_history
            self.context["last_edit_time"] = self.exited_at

        # 记录状态转换
        next_type = next_state.state_type.value if next_state else "none"
        self._log_state_transition("exit", next_state)

        logger.info(
            "editing_state_exited",
            edit_count=len(self.edit_history),
            duration=self._calculate_duration()
        )

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理编辑操作

        Args:
            input_data: 编辑输入数据，包含操作类型和参数

        Returns:
            编辑结果
        """
        operation = input_data.get("operation")
        parameters = input_data.get("parameters", {})

        if not operation:
            return {
                "success": False,
                "error": "未指定编辑操作",
                "state": self.state_type.value
            }

        try:
            # 根据操作类型执行相应的编辑
            if operation == "add_operation":
                result = await self._add_operation(parameters)
            elif operation == "modify_operation":
                result = await self._modify_operation(parameters)
            elif operation == "delete_operation":
                result = await self._delete_operation(parameters)
            elif operation == "update_parameters":
                result = await self._update_parameters(parameters)
            elif operation == "add_quality_requirement":
                result = await self._add_quality_requirement(parameters)
            else:
                return {
                    "success": False,
                    "error": f"不支持的编辑操作: {operation}",
                    "state": self.state_type.value
                }

            # 记录编辑历史
            edit_record = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "parameters": parameters,
                "result": result
            }
            self.edit_history.append(edit_record)

            # 更新当前文档
            if result.get("success") and "document" in result:
                self.current_document = result["document"]
                self.context["document"] = self.current_document

            logger.info(
                "edit_operation_processed",
                operation=operation,
                success=result.get("success", False)
            )

            return result

        except Exception as e:
            logger.error("edit_operation_failed", operation=operation, error=str(e))
            return {
                "success": False,
                "error": f"编辑操作失败: {str(e)}",
                "state": self.state_type.value
            }

    async def _add_operation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加工序

        Args:
            parameters: 工序参数

        Returns:
            添加结果
        """
        # 这里实现具体的添加工序逻辑
        # 暂时返回模拟结果
        operation_id = f"op_{len(self.edit_history) + 1}"
        new_operation = {
            "id": operation_id,
            "name": parameters.get("name", "新工序"),
            "description": parameters.get("description", ""),
            "tools": parameters.get("tools", []),
            "parameters": parameters.get("operation_params", {}),
            "sequence": parameters.get("sequence", 0)
        }

        # 更新文档
        if self.current_document:
            if "operations" not in self.current_document:
                self.current_document["operations"] = []
            self.current_document["operations"].append(new_operation)

        return {
            "success": True,
            "operation_id": operation_id,
            "message": "工序添加成功",
            "document": self.current_document
        }

    async def _modify_operation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        修改工序

        Args:
            parameters: 修改参数

        Returns:
            修改结果
        """
        operation_id = parameters.get("operation_id")
        if not operation_id:
            return {"success": False, "error": "未指定要修改的工序ID"}

        # 查找并修改工序
        if self.current_document and "operations" in self.current_document:
            for op in self.current_document["operations"]:
                if op.get("id") == operation_id:
                    # 更新工序信息
                    for key, value in parameters.get("updates", {}).items():
                        if key != "id":  # 不允许修改ID
                            op[key] = value
                    op["modified_at"] = datetime.now().isoformat()

                    return {
                        "success": True,
                        "operation_id": operation_id,
                        "message": "工序修改成功",
                        "document": self.current_document
                    }

        return {"success": False, "error": f"未找到工序: {operation_id}"}

    async def _delete_operation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        删除工序

        Args:
            parameters: 删除参数

        Returns:
            删除结果
        """
        operation_id = parameters.get("operation_id")
        if not operation_id:
            return {"success": False, "error": "未指定要删除的工序ID"}

        # 查找并删除工序
        if self.current_document and "operations" in self.current_document:
            original_count = len(self.current_document["operations"])
            self.current_document["operations"] = [
                op for op in self.current_document["operations"]
                if op.get("id") != operation_id
            ]

            if len(self.current_document["operations"]) < original_count:
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "message": "工序删除成功",
                    "document": self.current_document
                }

        return {"success": False, "error": f"未找到工序: {operation_id}"}

    async def _update_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新工艺参数

        Args:
            parameters: 参数更新

        Returns:
            更新结果
        """
        if not self.current_document:
            return {"success": False, "error": "当前没有活动文档"}

        # 更新文档参数
        if "parameters" not in self.current_document:
            self.current_document["parameters"] = {}

        updates = parameters.get("updates", {})
        self.current_document["parameters"].update(updates)

        return {
            "success": True,
            "updated_parameters": list(updates.keys()),
            "message": "工艺参数更新成功",
            "document": self.current_document
        }

    async def _add_quality_requirement(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加质量要求

        Args:
            parameters: 质量要求参数

        Returns:
            添加结果
        """
        if not self.current_document:
            return {"success": False, "error": "当前没有活动文档"}

        # 添加质量要求
        requirement = {
            "id": f"qr_{len(self.edit_history) + 1}",
            "description": parameters.get("description", ""),
            "standard": parameters.get("standard", ""),
            "tolerance": parameters.get("tolerance", ""),
            "inspection_method": parameters.get("inspection_method", "")
        }

        if "quality_requirements" not in self.current_document:
            self.current_document["quality_requirements"] = []

        self.current_document["quality_requirements"].append(requirement)

        return {
            "success": True,
            "requirement_id": requirement["id"],
            "message": "质量要求添加成功",
            "document": self.current_document
        }

    def can_transition_to(self, target_state_type: StateType) -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target_state_type: 目标状态类型

        Returns:
            是否可以转换
        """
        # 编辑状态可以转换到审核状态或生成状态
        allowed_transitions = {StateType.REVIEW, StateType.GENERATION}
        return target_state_type in allowed_transitions

    def get_edit_summary(self) -> Dict[str, Any]:
        """
        获取编辑摘要

        Returns:
            编辑摘要信息
        """
        return {
            "state_type": self.state_type.value,
            "edit_count": len(self.edit_history),
            "document_modified": self.current_document is not None,
            "last_edit": self.edit_history[-1] if self.edit_history else None,
            "duration": self._calculate_duration()
        }