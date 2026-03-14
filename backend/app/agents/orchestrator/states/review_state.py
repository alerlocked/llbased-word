"""
工艺文件辅助编辑系统 - 审核状态
处理工艺文件的审核和验证操作
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_state import BaseState, StateType
from app.shared.logging import get_logger

logger = get_logger(__name__)


class ReviewState(BaseState):
    """
    审核状态

    处理工艺文件的审核操作，包括：
    1. 检查工艺文件的完整性
    2. 验证工艺参数的正确性
    3. 检查合规性和标准符合性
    4. 收集审核意见和修改建议
    """

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """初始化审核状态"""
        super().__init__(StateType.REVIEW, context)
        self.review_items = []
        self.issues_found = []
        self.suggestions = []

    async def on_enter(self, previous_state: Optional[BaseState] = None):
        """
        进入审核状态

        Args:
            previous_state: 前一个状态
        """
        self.entered_at = datetime.now().isoformat()

        # 初始化审核上下文
        if "document" in self.context:
            document = self.context["document"]
            logger.info("review_state_entered", document_id=document.get("id", "unknown"))

            # 准备审核项目
            await self._prepare_review_items(document)
        else:
            logger.warning("review_state_entered_without_document")

        # 记录状态转换
        previous_type = previous_state.state_type.value if previous_state else "none"
        self._log_state_transition("enter", previous_state)

    async def on_exit(self, next_state: Optional[BaseState] = None):
        """
        退出审核状态

        Args:
            next_state: 下一个状态
        """
        self.exited_at = datetime.now().isoformat()

        # 保存审核结果到上下文
        review_summary = self.get_review_summary()
        self.context["review_summary"] = review_summary
        self.context["review_completed_at"] = self.exited_at

        # 记录状态转换
        next_type = next_state.state_type.value if next_state else "none"
        self._log_state_transition("exit", next_state)

        logger.info(
            "review_state_exited",
            issues_found=len(self.issues_found),
            suggestions=len(self.suggestions),
            duration=self._calculate_duration()
        )

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理审核操作

        Args:
            input_data: 审核输入数据

        Returns:
            审核结果
        """
        action = input_data.get("action")
        parameters = input_data.get("parameters", {})

        if not action:
            return {
                "success": False,
                "error": "未指定审核操作",
                "state": self.state_type.value
            }

        try:
            if action == "check_completeness":
                result = await self._check_completeness(parameters)
            elif action == "validate_parameters":
                result = await self._validate_parameters(parameters)
            elif action == "check_compliance":
                result = await self._check_compliance(parameters)
            elif action == "add_review_comment":
                result = await self._add_review_comment(parameters)
            elif action == "approve_document":
                result = await self._approve_document(parameters)
            elif action == "request_revision":
                result = await self._request_revision(parameters)
            else:
                return {
                    "success": False,
                    "error": f"不支持的审核操作: {action}",
                    "state": self.state_type.value
                }

            logger.info(
                "review_action_processed",
                action=action,
                success=result.get("success", False)
            )

            return result

        except Exception as e:
            logger.error("review_action_failed", action=action, error=str(e))
            return {
                "success": False,
                "error": f"审核操作失败: {str(e)}",
                "state": self.state_type.value
            }

    async def _prepare_review_items(self, document: Dict[str, Any]):
        """
        准备审核项目

        Args:
            document: 工艺文档
        """
        self.review_items = []

        # 1. 检查文档基本信息
        self.review_items.append({
            "type": "basic_info",
            "description": "检查文档基本信息完整性",
            "required_fields": ["id", "name", "template_id", "part_info"],
            "document_fields": list(document.keys())
        })

        # 2. 检查工序列表
        if "operations" in document:
            self.review_items.append({
                "type": "operations",
                "description": f"检查{len(document['operations'])}个工序",
                "count": len(document["operations"]),
                "sample": document["operations"][0] if document["operations"] else None
            })

        # 3. 检查工艺参数
        if "parameters" in document:
            self.review_items.append({
                "type": "parameters",
                "description": f"检查{len(document['parameters'])}个工艺参数",
                "count": len(document["parameters"]),
                "keys": list(document["parameters"].keys())
            })

        # 4. 检查质量要求
        if "quality_requirements" in document:
            self.review_items.append({
                "type": "quality_requirements",
                "description": f"检查{len(document['quality_requirements'])}个质量要求",
                "count": len(document["quality_requirements"])
            })

        logger.debug("review_items_prepared", item_count=len(self.review_items))

    async def _check_completeness(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查文档完整性

        Args:
            parameters: 检查参数

        Returns:
            完整性检查结果
        """
        document = self.context.get("document")
        if not document:
            return {"success": False, "error": "没有可检查的文档"}

        missing_fields = []
        required_fields = ["id", "name", "template_id", "part_info"]

        for field in required_fields:
            if field not in document or not document[field]:
                missing_fields.append(field)

        if missing_fields:
            issue = {
                "type": "missing_field",
                "severity": "high",
                "fields": missing_fields,
                "description": f"缺少必要字段: {', '.join(missing_fields)}"
            }
            self.issues_found.append(issue)

            return {
                "success": False,
                "issues": [issue],
                "message": "文档不完整，缺少必要字段"
            }
        else:
            return {
                "success": True,
                "message": "文档基本信息完整",
                "checked_fields": required_fields
            }

    async def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证工艺参数

        Args:
            parameters: 验证参数

        Returns:
            验证结果
        """
        document = self.context.get("document")
        if not document or "parameters" not in document:
            return {"success": False, "error": "没有可验证的工艺参数"}

        param_issues = []
        suggestions = []

        # 简单的参数验证逻辑
        # 这里可以根据实际业务规则扩展
        for param_name, param_value in document["parameters"].items():
            # 检查参数值是否为空
            if param_value is None or param_value == "":
                issue = {
                    "type": "empty_parameter",
                    "severity": "medium",
                    "parameter": param_name,
                    "description": f"参数 '{param_name}' 值为空"
                }
                param_issues.append(issue)

            # 检查数值参数的合理性
            if isinstance(param_value, (int, float)):
                # 这里可以添加数值范围检查等
                pass

        if param_issues:
            self.issues_found.extend(param_issues)
            return {
                "success": False,
                "issues": param_issues,
                "message": f"发现{len(param_issues)}个参数问题"
            }
        else:
            return {
                "success": True,
                "message": "工艺参数验证通过",
                "parameter_count": len(document["parameters"])
            }

    async def _check_compliance(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查合规性

        Args:
            parameters: 合规检查参数

        Returns:
            合规检查结果
        """
        # 这里实现具体的合规检查逻辑
        # 暂时返回模拟结果
        compliance_rules = parameters.get("rules", ["basic_standard"])

        issues = []
        for rule in compliance_rules:
            # 模拟检查结果
            if rule == "basic_standard":
                # 基本标准检查
                pass
            elif rule == "safety_requirement":
                # 安全检查
                pass

        if issues:
            self.issues_found.extend(issues)
            return {
                "success": False,
                "issues": issues,
                "message": f"合规检查发现{len(issues)}个问题"
            }
        else:
            return {
                "success": True,
                "message": "合规检查通过",
                "checked_rules": compliance_rules
            }

    async def _add_review_comment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加审核意见

        Args:
            parameters: 意见参数

        Returns:
            添加结果
        """
        comment = parameters.get("comment")
        if not comment:
            return {"success": False, "error": "审核意见不能为空"}

        review_comment = {
            "id": f"comment_{len(self.suggestions) + 1}",
            "timestamp": datetime.now().isoformat(),
            "comment": comment,
            "category": parameters.get("category", "general"),
            "priority": parameters.get("priority", "medium")
        }

        self.suggestions.append(review_comment)

        return {
            "success": True,
            "comment_id": review_comment["id"],
            "message": "审核意见已添加"
        }

    async def _approve_document(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        批准文档

        Args:
            parameters: 批准参数

        Returns:
            批准结果
        """
        # 检查是否有未解决的问题
        if self.issues_found:
            high_priority_issues = [i for i in self.issues_found if i.get("severity") == "high"]
            if high_priority_issues:
                return {
                    "success": False,
                    "error": "存在高优先级问题，不能批准",
                    "high_priority_issues": len(high_priority_issues)
                }

        # 更新文档状态
        document = self.context.get("document")
        if document:
            document["status"] = "approved"
            document["approved_at"] = datetime.now().isoformat()
            document["approver"] = parameters.get("approver", "system")
            document["version"] = document.get("version", 0) + 1

        return {
            "success": True,
            "message": "文档已批准",
            "document_status": "approved",
            "approval_time": datetime.now().isoformat()
        }

    async def _request_revision(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        请求修订

        Args:
            parameters: 修订请求参数

        Returns:
            请求结果
        """
        revision_reason = parameters.get("reason", "需要进一步修改")
        required_changes = parameters.get("required_changes", [])

        revision_request = {
            "id": f"revision_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "reason": revision_reason,
            "required_changes": required_changes,
            "issues_to_resolve": [issue.get("description") for issue in self.issues_found],
            "suggestions": [suggestion.get("comment") for suggestion in self.suggestions]
        }

        # 更新文档状态
        document = self.context.get("document")
        if document:
            document["status"] = "revision_required"
            document["revision_request"] = revision_request

        return {
            "success": True,
            "message": "修订请求已提交",
            "revision_request": revision_request,
            "document_status": "revision_required"
        }

    def can_transition_to(self, target_state_type: StateType) -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target_state_type: 目标状态类型

        Returns:
            是否可以转换
        """
        # 审核状态可以转换到编辑状态（如果需要修订）或完成状态
        allowed_transitions = {StateType.EDITING, StateType.COMPLETION}
        return target_state_type in allowed_transitions

    def get_review_summary(self) -> Dict[str, Any]:
        """
        获取审核摘要

        Returns:
            审核摘要信息
        """
        return {
            "state_type": self.state_type.value,
            "review_items_count": len(self.review_items),
            "issues_found": len(self.issues_found),
            "suggestions_count": len(self.suggestions),
            "high_priority_issues": len([i for i in self.issues_found if i.get("severity") == "high"]),
            "review_duration": self._calculate_duration(),
            "completion_status": "completed" if self.exited_at else "in_progress"
        }