"""
术语映射 Tool

将工艺师的自然语言描述转换为标准工艺术语
"""
from typing import Dict, Any, Optional, List
from app.agents.core import ToolRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@ToolRegistry.register("terminology_mapper")
class TerminologyTool:
    """
    术语映射工具

    负责将用户输入的自然语言描述转换为标准的工艺术语
    """

    name = "terminology_mapper"
    description = "将自然语言描述映射为标准工艺术语，支持术语标准化和一致性检查"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化术语映射工具

        Args:
            config: 配置参数
                - similarity_threshold: 相似度阈值（默认0.85）
                - max_suggestions: 最大建议数量（默认3）
                - fuzzy_matching_enabled: 是否启用模糊匹配（默认True）
        """
        self.config = config or {}
        self.similarity_threshold = self.config.get("similarity_threshold", 0.85)
        self.max_suggestions = self.config.get("max_suggestions", 3)
        self.fuzzy_matching_enabled = self.config.get("fuzzy_matching_enabled", True)

        # 延迟加载 TerminologyMapper
        self._mapper = None

        logger.info(
            "terminology_tool_initialized",
            similarity_threshold=self.similarity_threshold
        )

    @property
    def mapper(self):
        """延迟加载 TerminologyMapper"""
        if self._mapper is None:
            try:
                from app.tools.terminology_mapper import TerminologyMapper
                self._mapper = TerminologyMapper(self.config)
            except Exception as e:
                logger.error("terminology_mapper_load_failed", error=str(e))
        return self._mapper

    async def execute(
        self,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行术语映射

        Args:
            input_data: 输入数据，可以是字符串或字典
                - 字符串: 待映射的文本
                - 字典: {"content": str, "target_standard": str}
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "original_text": str,
                "mapped_text": str,
                "mappings": [
                    {
                        "original": str,
                        "standard": str,
                        "confidence": float,
                        "standard_type": str
                    }
                ],
                "suggestions": List[str]
            }
        """
        try:
            # 解析输入
            if isinstance(input_data, str):
                text = input_data
                target_standard = "enterprise_standard"
            elif isinstance(input_data, dict):
                text = input_data.get("content", "")
                target_standard = input_data.get("target_standard", "enterprise_standard")
            else:
                return {
                    "success": False,
                    "error": "输入数据格式错误",
                    "error_code": "INVALID_INPUT"
                }

            if not text:
                return {
                    "success": False,
                    "error": "文本内容不能为空",
                    "error_code": "EMPTY_TEXT"
                }

            # 执行术语映射
            if self.mapper is None:
                return self._mock_mapping(text, target_standard)

            # 调用实际映射器
            result = await self._map_terms(text, target_standard)

            logger.info(
                "terminology_mapping_completed",
                text_length=len(text),
                mappings_count=len(result.get("mappings", []))
            )

            return result

        except Exception as e:
            logger.error("terminology_mapping_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "MAPPING_FAILED"
            }

    async def _map_terms(
        self,
        text: str,
        target_standard: str
    ) -> Dict[str, Any]:
        """
        执行实际术语映射

        Args:
            text: 待映射文本
            target_standard: 目标标准

        Returns:
            映射结果
        """
        # 调用 TerminologyMapper
        mapping_result = await self.mapper.map_terms(
            source_text=text,
            target_standard=target_standard,
            fuzzy_matching=self.fuzzy_matching_enabled,
            confidence_threshold=self.similarity_threshold
        )

        if not mapping_result or not mapping_result.get("success"):
            return {
                "success": False,
                "error": mapping_result.get("error", "术语映射失败"),
                "error_code": "MAPPING_FAILED"
            }

        return {
            "success": True,
            "original_text": text,
            "mapped_text": mapping_result.get("mapped_text", text),
            "mappings": mapping_result.get("mappings", []),
            "suggestions": mapping_result.get("suggestions", [])[:self.max_suggestions]
        }

    def _mock_mapping(self, text: str, target_standard: str) -> Dict[str, Any]:
        """
        模拟术语映射

        Args:
            text: 待映射文本
            target_standard: 目标标准

        Returns:
            模拟结果
        """
        # 简单的术语替换示例
        common_terms = {
            "剥线": "导线剥线",
            "压接": "端子压接",
            "焊接": "电子束焊接",
            "装配": "电缆装配"
        }

        mapped_text = text
        mappings = []

        for original, standard in common_terms.items():
            if original in text:
                mapped_text = mapped_text.replace(original, standard)
                mappings.append({
                    "original": original,
                    "standard": standard,
                    "confidence": 0.95,
                    "standard_type": "process_term"
                })

        return {
            "success": True,
            "original_text": text,
            "mapped_text": mapped_text,
            "mappings": mappings,
            "suggestions": [],
            "note": "TerminologyMapper 不可用，返回模拟结果"
        }
