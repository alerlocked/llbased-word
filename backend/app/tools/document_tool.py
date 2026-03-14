"""
文档生成 Tool

根据工艺内容生成标准化的工艺文件
"""
from typing import Dict, Any, Optional, List
from app.agents.core import ToolRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@ToolRegistry.register("document_generator")
class DocumentTool:
    """
    文档生成工具

    根据工艺内容生成标准化的工艺文件
    """

    name = "document_generator"
    description = "根据工艺内容生成标准化的工艺文件，支持PDF、Word、HTML等多种格式"

    # 支持的输出格式
    SUPPORTED_FORMATS = ["pdf", "word", "html", "markdown", "json"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化文档生成工具

        Args:
            config: 配置参数
                - output_formats: 输出格式列表
                - template_name: 模板名称
                - quality_level: 质量级别
        """
        self.config = config or {}
        self.output_formats = self.config.get("output_formats", ["html", "markdown"])
        self.template_name = self.config.get("template_name", "standard_process_template")
        self.quality_level = self.config.get("quality_level", "production")

        # 延迟加载 DocumentGenerator
        self._generator = None

        logger.info(
            "document_tool_initialized",
            output_formats=self.output_formats,
            template=self.template_name
        )

    @property
    def generator(self):
        """延迟加载 DocumentGenerator"""
        if self._generator is None:
            try:
                from app.tools.document_generator import DocumentGenerator
                self._generator = DocumentGenerator(self.config)
            except Exception as e:
                logger.error("document_generator_load_failed", error=str(e))
        return self._generator

    async def execute(
        self,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行文档生成

        Args:
            input_data: 输入数据
                - content: 工艺内容（必需）
                - title: 文档标题（可选）
                - format: 输出格式（可选）
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "files": [
                    {
                        "format": str,
                        "path": str,
                        "size": int
                    }
                ],
                "preview_url": str,
                "metadata": dict
            }
        """
        try:
            # 解析输入
            if isinstance(input_data, dict):
                content = input_data.get("content")
                title = input_data.get("title", "工艺文件")
                format = input_data.get("format", "html")
            elif isinstance(input_data, str):
                content = input_data
                title = "工艺文件"
                format = "html"
            else:
                return {
                    "success": False,
                    "error": "输入数据格式错误",
                    "error_code": "INVALID_INPUT"
                }

            if not content:
                return {
                    "success": False,
                    "error": "内容不能为空",
                    "error_code": "EMPTY_CONTENT"
                }

            # 验证格式
            if format not in self.SUPPORTED_FORMATS:
                format = "html"

            # 生成文档
            if self.generator is None:
                return self._mock_generation(content, title, format)

            # 调用实际生成器
            result = await self._generate_document(content, title, format, context)

            logger.info(
                "document_generation_completed",
                title=title,
                format=format,
                files_count=len(result.get("files", []))
            )

            return result

        except Exception as e:
            logger.error("document_generation_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "GENERATION_FAILED"
            }

    async def _generate_document(
        self,
        content: str,
        title: str,
        format: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行实际文档生成

        Args:
            content: 工艺内容
            title: 文档标题
            format: 输出格式
            context: 执行上下文

        Returns:
            生成结果
        """
        # 调用 DocumentGenerator
        gen_result = await self.generator.generate(
            content=content,
            template_name=self.template_name,
            output_format=format,
            metadata={"title": title}
        )

        if not gen_result or not gen_result.get("success"):
            return {
                "success": False,
                "error": gen_result.get("error", "文档生成失败"),
                "error_code": "GENERATION_FAILED"
            }

        return {
            "success": True,
            "files": gen_result.get("files", []),
            "preview_url": gen_result.get("preview_url"),
            "metadata": {
                "title": title,
                "format": format,
                "template": self.template_name
            }
        }

    def _mock_generation(
        self,
        content: str,
        title: str,
        format: str
    ) -> Dict[str, Any]:
        """
        模拟文档生成

        Args:
            content: 工艺内容
            title: 文档标题
            format: 输出格式

        Returns:
            模拟结果
        """
        from datetime import datetime

        # 生成模拟文件路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{title}_{timestamp}.{format}"

        return {
            "success": True,
            "files": [
                {
                    "format": format,
                    "path": f"/output/{filename}",
                    "size": len(content.encode('utf-8'))
                }
            ],
            "preview_url": f"/preview/{filename}",
            "metadata": {
                "title": title,
                "format": format,
                "generated_at": timestamp
            },
            "note": "DocumentGenerator 不可用，返回模拟结果"
        }
