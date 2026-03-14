"""
工艺文件辅助编辑系统 - 文档生成工具
实现工艺文件的标准化生成，支持多种输出格式
"""
from typing import Dict, Any, Optional, List, Union
import json
import os
from pathlib import Path
from datetime import datetime

from app.shared.logging import get_logger

logger = get_logger(__name__)


class DocumentGenerator:
    """
    文档生成工具

    负责具体的文档生成逻辑，
    支持PDF、Word、JSON等多种格式
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化文档生成工具

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.templates_dir = self.config.get("templates_dir", "backend/data/templates/process_templates")
        self.output_dir = self.config.get("output_dir", "data/generated_documents")
        self.cache_enabled = self.config.get("cache_enabled", True)

        # 加载模板
        self.available_templates = self._load_available_templates()

        logger.info(
            "document_generator_initialized",
            templates_dir=self.templates_dir,
            output_dir=self.output_dir,
            template_count=len(self.available_templates)
        )

    def _load_available_templates(self) -> List[str]:
        """
        加载可用模板

        Returns:
            模板列表
        """
        templates = []

        try:
            templates_path = Path(self.templates_dir)
            if not templates_path.exists():
                logger.warning("templates_directory_not_found", path=self.templates_dir)
                return templates

            # 查找所有模板文件和目录
            for item in templates_path.iterdir():
                if item.is_dir() or item.suffix in ['.json', '.template']:
                    templates.append(item.name)

            if not templates:
                logger.warning("no_templates_found", path=self.templates_dir)

        except Exception as e:
            logger.error("templates_loading_failed", error=str(e))

        return templates

    async def generate_document(
        self,
        content: Dict[str, Any],
        template_name: str = "standard_process_template",
        output_formats: List[str] = None,
        quality_level: str = "production",
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        生成文档

        Args:
            content: 工艺内容
            template_name: 模板名称
            output_formats: 输出格式列表
            quality_level: 质量级别
            include_metadata: 是否包含元数据

        Returns:
            生成结果
        """
        try:
            # 验证模板
            if template_name not in self.available_templates:
                return {
                    "success": False,
                    "error": f"模板不存在: {template_name}",
                    "error_code": "TEMPLATE_NOT_FOUND"
                }

            # 验证输出格式
            supported_formats = await self.get_supported_formats()
            output_formats = output_formats or ["pdf"]
            invalid_formats = [f for f in output_formats if f not in supported_formats]
            if invalid_formats:
                return {
                    "success": False,
                    "error": f"不支持的输出格式: {', '.join(invalid_formats)}",
                    "error_code": "UNSUPPORTED_FORMAT"
                }

            # 准备输出目录
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # 生成文件
            generated_files = []
            for format_type in output_formats:
                file_info = await self._generate_file_by_format(
                    content, template_name, format_type, quality_level, output_path
                )
                if file_info:
                    generated_files.append(file_info)

            # 构建元数据
            metadata = {}
            if include_metadata:
                metadata = await self._build_metadata(content, template_name, output_formats, quality_level)

            return {
                "success": True,
                "files": generated_files,
                "metadata": metadata
            }

        except Exception as e:
            logger.error("document_generation_failed", error=str(e), content_id=content.get("id", "unknown"))
            return {
                "success": False,
                "error": f"文档生成失败: {str(e)}",
                "error_code": "GENERATION_EXCEPTION"
            }

    async def _generate_file_by_format(
        self,
        content: Dict[str, Any],
        template_name: str,
        format_type: str,
        quality_level: str,
        output_path: Path
    ) -> Optional[Dict[str, Any]]:
        """
        根据格式生成文件

        Args:
            content: 工艺内容
            template_name: 模板名称
            format_type: 格式类型
            quality_level: 质量级别
            output_path: 输出路径

        Returns:
            文件信息
        """
        try:
            content_id = content.get("id", f"doc_{datetime.now().timestamp()}")
            filename = f"{content_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
            filepath = output_path / filename

            # 根据格式生成内容
            if format_type == "json":
                file_content = await self._generate_json_content(content, template_name, quality_level)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(file_content, f, ensure_ascii=False, indent=2)
            elif format_type == "pdf":
                file_content = await self._generate_pdf_content(content, template_name, quality_level)
                # 这里应该调用PDF生成库
                # 目前创建空文件作为占位符
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"PDF content placeholder for {content_id}")
            elif format_type == "word":
                file_content = await self._generate_word_content(content, template_name, quality_level)
                # 这里应该调用Word生成库
                # 目前创建空文件作为占位符
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Word content placeholder for {content_id}")
            else:
                logger.warning("unsupported_format", format_type=format_type)
                return None

            # 获取文件大小
            file_size = filepath.stat().st_size

            file_info = {
                "id": f"file_{datetime.now().timestamp()}",
                "filename": filename,
                "filepath": str(filepath),
                "format": format_type,
                "size_kb": file_size // 1024,
                "created_at": datetime.now().isoformat(),
                "quality_level": quality_level,
                "template_used": template_name
            }

            logger.debug("file_generated", filename=filename, format_type=format_type, size_kb=file_info["size_kb"])
            return file_info

        except Exception as e:
            logger.error("file_generation_failed", error=str(e), format_type=format_type, content_id=content.get("id", "unknown"))
            return None

    async def _generate_json_content(self, content: Dict[str, Any], template_name: str, quality_level: str) -> Dict[str, Any]:
        """
        生成JSON内容

        Args:
            content: 工艺内容
            template_name: 模板名称
            quality_level: 质量级别

        Returns:
            JSON内容
        """
        json_content = content.copy()
        json_content.update({
            "generated_at": datetime.now().isoformat(),
            "template": template_name,
            "quality_level": quality_level,
            "format": "json"
        })
        return json_content

    async def _generate_pdf_content(self, content: Dict[str, Any], template_name: str, quality_level: str) -> str:
        """
        生成PDF内容

        Args:
            content: 工艺内容
            template_name: 模板名称
            quality_level: 质量级别

        Returns:
            PDF内容
        """
        # 这里应该实现具体的PDF生成逻辑
        # 目前返回占位符
        return f"PDF content for {content.get('id', 'unknown')}"

    async def _generate_word_content(self, content: Dict[str, Any], template_name: str, quality_level: str) -> str:
        """
        生成Word内容

        Args:
            content: 工艺内容
            template_name: 模板名称
            quality_level: 质量级别

        Returns:
            Word内容
        """
        # 这里应该实现具体的Word生成逻辑
        # 目前返回占位符
        return f"Word content for {content.get('id', 'unknown')}"

    async def _build_metadata(self, content: Dict[str, Any], template_name: str, output_formats: List[str], quality_level: str) -> Dict[str, Any]:
        """
        构建元数据

        Args:
            content: 工艺内容
            template_name: 模板名称
            output_formats: 输出格式列表
            quality_level: 质量级别

        Returns:
            元数据
        """
        metadata = {
            "document_id": content.get("id", "unknown"),
            "document_name": content.get("name", "未命名工艺文件"),
            "template_used": template_name,
            "output_formats": output_formats,
            "quality_level": quality_level,
            "generated_at": datetime.now().isoformat(),
            "generator_version": "1.0.0",
            "content_summary": {
                "operations_count": len(content.get("operations", [])),
                "parameters_count": len(content.get("parameters", {})),
                "quality_requirements_count": len(content.get("quality_requirements", []))
            }
        }

        return metadata

    async def get_supported_formats(self) -> List[str]:
        """
        获取支持的输出格式

        Returns:
            支持的格式列表
        """
        return ["json", "pdf", "word"]

    async def get_available_templates(self) -> List[str]:
        """
        获取可用的模板

        Returns:
            模板列表
        """
        return self.available_templates

    async def add_template(self, template_name: str, template_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加模板

        Args:
            template_name: 模板名称
            template_content: 模板内容

        Returns:
            添加结果
        """
        try:
            templates_path = Path(self.templates_dir)
            templates_path.mkdir(parents=True, exist_ok=True)

            template_file = templates_path / f"{template_name}.json"
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_content, f, ensure_ascii=False, indent=2)

            # 重新加载模板
            self.available_templates = self._load_available_templates()

            logger.info("template_added", template_name=template_name)
            return {
                "success": True,
                "message": f"模板 '{template_name}' 已添加"
            }

        except Exception as e:
            logger.error("template_addition_failed", error=str(e), template_name=template_name)
            return {
                "success": False,
                "error": f"模板添加失败: {str(e)}",
                "error_code": "TEMPLATE_ADDITION_EXCEPTION"
            }