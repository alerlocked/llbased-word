"""
信息完整性评估器

评估当前上下文是否有足够的信息来完成任务
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.shared.logging import get_logger
from app.agents.orchestrator.info_requirements import (
    get_info_requirements,
    detect_task_type,
    InfoItem,
    InfoPriority,
    TaskInfoRequirements
)

logger = get_logger(__name__)


@dataclass
class MissingInfo:
    """缺失的信息"""
    item: InfoItem
    found_in_context: bool = False
    extracted_value: Optional[str] = None


@dataclass
class AssessmentResult:
    """评估结果"""
    is_complete: bool
    task_type: str
    missing_high_priority: List[MissingInfo]
    missing_medium_priority: List[MissingInfo]
    missing_low_priority: List[MissingInfo]
    available_info: Dict[str, Any]
    assessment_confidence: float
    can_proceed_with_defaults: bool


class InfoAssessor:
    """
    信息完整性评估器

    评估当前上下文是否有足够的信息来完成任务
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化评估器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.strict_mode = self.config.get("strict_mode", False)

        # 常见的信息提取规则
        self._extraction_rules = {
            "螺钉规格": self._extract_screw_spec,
            "材料": self._extract_material,
            "强度等级": self._extract_strength_grade,
            "被连接件材料": self._extract_connected_material,
        }

        logger.info("info_assessor_initialized", strict_mode=self.strict_mode)

    async def assess(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AssessmentResult:
        """
        评估信息完整性

        Args:
            intent: 意图识别结果
            context: 当前上下文

        Returns:
            评估结果
        """
        # 1. 确定任务类型
        task_type = self._determine_task_type(intent, context)
        if not task_type:
            # 无法确定任务类型，返回需要更多信息
            return AssessmentResult(
                is_complete=False,
                task_type="unknown",
                missing_high_priority=[],
                missing_medium_priority=[],
                missing_low_priority=[],
                available_info={},
                assessment_confidence=0.0,
                can_proceed_with_defaults=False
            )

        # 2. 获取信息需求模板
        requirements = get_info_requirements(task_type)
        if not requirements:
            # 没有找到需求模板，假设信息完整
            return AssessmentResult(
                is_complete=True,
                task_type=task_type,
                missing_high_priority=[],
                missing_medium_priority=[],
                missing_low_priority=[],
                available_info={},
                assessment_confidence=1.0,
                can_proceed_with_defaults=True
            )

        # 3. 从上下文中提取已有信息
        available_info = self._extract_available_info(
            requirements,
            intent,
            context
        )

        # 4. 检查缺失信息
        missing_high = []
        missing_medium = []
        missing_low = []

        for item in requirements.required:
            missing = self._check_missing(item, available_info)
            if missing:
                if item.priority == InfoPriority.HIGH:
                    missing_high.append(missing)
                elif item.priority == InfoPriority.MEDIUM:
                    missing_medium.append(missing)
                else:
                    missing_low.append(missing)

        for item in requirements.optional:
            missing = self._check_missing(item, available_info)
            if missing:
                if item.priority == InfoPriority.HIGH:
                    missing_high.append(missing)
                elif item.priority == InfoPriority.MEDIUM:
                    missing_medium.append(missing)
                else:
                    missing_low.append(missing)

        # 5. 判断是否完整
        is_complete = len(missing_high) == 0

        # 如果有默认值可用，检查是否可以继续
        can_proceed_with_defaults = is_complete or (
            len(missing_high) == 0 and
            all(m.item.default_value for m in missing_medium)
        )

        # 6. 计算置信度
        total_required = len(requirements.required)
        found_required = total_required - len([m for m in missing_high + missing_medium if m.item in requirements.required])
        confidence = found_required / total_required if total_required > 0 else 1.0

        logger.info(
            "info_assessment_completed",
            task_type=task_type,
            is_complete=is_complete,
            missing_high=len(missing_high),
            missing_medium=len(missing_medium),
            confidence=confidence
        )

        return AssessmentResult(
            is_complete=is_complete,
            task_type=task_type,
            missing_high_priority=missing_high,
            missing_medium_priority=missing_medium,
            missing_low_priority=missing_low,
            available_info=available_info,
            assessment_confidence=confidence,
            can_proceed_with_defaults=can_proceed_with_defaults
        )

    def _determine_task_type(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        确定任务类型

        Args:
            intent: 意图识别结果
            context: 上下文

        Returns:
            任务类型
        """
        # 首先从意图中获取
        intent_type = intent.get("type")
        if intent_type:
            # 映射意图类型到任务类型
            type_mapping = {
                "create_document": "create",
                "edit_document": "edit",
                "calculate": "calculate",
                "proofread": "proofread",
                "review": "review",
            }
            return type_mapping.get(intent_type, intent_type)

        # 从用户输入中检测
        user_input = context.get("user_input", "")
        if user_input:
            return detect_task_type(user_input)

        return None

    def _extract_available_info(
        self,
        requirements: TaskInfoRequirements,
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        从上下文中提取已有信息

        Args:
            requirements: 信息需求
            intent: 意图识别结果
            context: 上下文

        Returns:
            已有的信息字典
        """
        available = {}

        # 从意图实体中提取
        entities = intent.get("entities", {})
        if entities:
            available.update(entities)

        # 从上下文中提取
        context_info = context.get("document_context", {})
        if context_info:
            # 提取文档元数据
            metadata = context_info.get("metadata", {})
            if metadata:
                available["document_title"] = metadata.get("title")
                available["document_type"] = metadata.get("doc_type")

        # 从对话历史中提取
        dialog_context = context.get("dialog_context", {})
        if dialog_context:
            collected = dialog_context.get("collected_info", {})
            available.update(collected)

        # 使用提取规则进一步提取
        user_input = context.get("user_input", "")
        if user_input:
            for info_name, extract_func in self._extraction_rules.items():
                value = extract_func(user_input)
                if value:
                    available[info_name] = value

        return available

    def _check_missing(
        self,
        item: InfoItem,
        available_info: Dict[str, Any]
    ) -> Optional[MissingInfo]:
        """
        检查单个信息项是否缺失

        Args:
            item: 信息项
            available_info: 已有信息

        Returns:
            如果缺失则返回MissingInfo，否则返回None
        """
        # 检查是否在已有信息中
        for key, value in available_info.items():
            if item.matches(key) and value:
                return None

        # 检查是否有默认值
        if item.default_value:
            return None

        # 缺失
        return MissingInfo(
            item=item,
            found_in_context=False,
            extracted_value=None
        )

    # ============== 信息提取规则 ==============

    def _extract_screw_spec(self, text: str) -> Optional[str]:
        """提取螺钉规格"""
        import re
        # 匹配 M4, M5, M6, M8 等格式
        match = re.search(r'\bM\d+\.?\d*\b', text, re.IGNORECASE)
        return match.group(0) if match else None

    def _extract_material(self, text: str) -> Optional[str]:
        """提取材料类型"""
        materials = ["不锈钢", "碳钢", "合金钢", "铝合金", "钛合金", "铜", "黄铜", "青铜"]
        for material in materials:
            if material in text:
                return material
        return None

    def _extract_strength_grade(self, text: str) -> Optional[str]:
        """提取强度等级"""
        import re
        # 匹配 4.8, 8.8, 10.9, A2-70, A4-80 等
        patterns = [
            r'\b\d+\.\d+\b',  # 4.8, 8.8, 10.9
            r'\bA[24]-\d+\b',  # A2-70, A4-80
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _extract_connected_material(self, text: str) -> Optional[str]:
        """提取被连接件材料"""
        materials = ["铝合金", "钢", "钛合金", "铜", "铸铁", "塑料", "复合材料"]
        keywords = ["被连接件", "连接件", "基体"]
        for kw in keywords:
            if kw in text:
                for material in materials:
                    if material in text:
                        return material
        return None

    def get_missing_info_message(
        self,
        assessment: AssessmentResult
    ) -> Dict[str, Any]:
        """
        生成缺失信息的用户消息

        Args:
            assessment: 评估结果

        Returns:
            包含消息和缺失项列表的字典
        """
        if assessment.is_complete:
            return {
                "needs_more_info": False,
                "message": "信息已完整，可以开始处理",
                "missing_items": []
            }

        # 组织缺失信息
        missing_items = []

        for missing in assessment.missing_high_priority:
            missing_items.append({
                "name": missing.item.name,
                "description": missing.item.description,
                "example": missing.item.example,
                "impact": missing.item.impact or "影响处理结果",
                "priority": "high",
                "input_type": missing.item.input_type.value
            })

        for missing in assessment.missing_medium_priority:
            missing_items.append({
                "name": missing.item.name,
                "description": missing.item.description,
                "example": missing.item.example,
                "impact": missing.item.impact or "影响结果质量",
                "priority": "medium",
                "input_type": missing.item.input_type.value
            })

        # 生成消息
        high_count = len(assessment.missing_high_priority)
        medium_count = len(assessment.missing_medium_priority)

        message_parts = []
        if high_count > 0:
            message_parts.append(f"检测到 {high_count} 项高优先级信息缺失")
        if medium_count > 0:
            message_parts.append(f"{medium_count} 项中优先级信息缺失")

        message = "，".join(message_parts) if message_parts else "检测到信息缺失"
        message += "，需要您确认后再继续处理。"

        return {
            "needs_more_info": True,
            "message": message,
            "missing_items": missing_items,
            "can_skip": assessment.can_proceed_with_defaults
        }
