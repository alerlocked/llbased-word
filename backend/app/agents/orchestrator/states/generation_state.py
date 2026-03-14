"""
工艺文件辅助编辑系统 - 生成状态
处理工艺文件的生成和导出操作
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from .base_state import BaseState, StateType
from app.shared.logging import get_logger

logger = get_logger(__name__)


class GenerationState(BaseState):
    """
    生成状态

    处理工艺文件的生成操作，包括：
    1. 格式化工艺文档
    2. 应用模板
    3. 生成输出文件（PDF、Word等）
    4. 准备导出到PDM系统
    """

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """初始化生成状态"""
        super().__init__(StateType.GENERATION, context)
        self.generated_files = []
        self.export_formats = []
        self.generation_log = []

    async def on_enter(self, previous_state: Optional[BaseState] = None):
        """
        进入生成状态

        Args:
            previous_state: 前一个状态
        """
        self.entered_at = datetime.now().isoformat()

        # 初始化生成上下文
        document = self.context.get("document")
        if document:
            logger.info("generation_state_entered", document_id=document.get("id", "unknown"))
        else:
            logger.warning("generation_state_entered_without_document")

        # 设置默认导出格式
        self.export_formats = self.context.get("export_formats", ["json", "pdf"])

        # 记录状态转换
        previous_type = previous_state.state_type.value if previous_state else "none"
        self._log_state_transition("enter", previous_state)

    async def on_exit(self, next_state: Optional[BaseState] = None):
        """
        退出生成状态

        Args:
            next_state: 下一个状态
        """
        self.exited_at = datetime.now().isoformat()

        # 保存生成结果到上下文
        generation_summary = self.get_generation_summary()
        self.context["generation_summary"] = generation_summary
        self.context["generation_completed_at"] = self.exited_at

        # 记录状态转换
        next_type = next_state.state_type.value if next_state else "none"
        self._log_state_transition("exit", next_state)

        logger.info(
            "generation_state_exited",
            files_generated=len(self.generated_files),
            formats=self.export_formats,
            duration=self._calculate_duration()
        )

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理生成操作

        Args:
            input_data: 生成输入数据

        Returns:
            生成结果
        """
        action = input_data.get("action")
        parameters = input_data.get("parameters", {})

        if not action:
            return {
                "success": False,
                "error": "未指定生成操作",
                "state": self.state_type.value
            }

        try:
            if action == "format_document":
                result = await self._format_document(parameters)
            elif action == "apply_template":
                result = await self._apply_template(parameters)
            elif action == "generate_pdf":
                result = await self._generate_pdf(parameters)
            elif action == "generate_word":
                result = await self._generate_word(parameters)
            elif action == "export_to_pdm":
                result = await self._export_to_pdm(parameters)
            elif action == "set_export_formats":
                result = await self._set_export_formats(parameters)
            else:
                return {
                    "success": False,
                    "error": f"不支持的生成操作: {action}",
                    "state": self.state_type.value
                }

            # 记录生成日志
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "parameters": parameters,
                "result": {"success": result.get("success", False)}
            }
            self.generation_log.append(log_entry)

            logger.info(
                "generation_action_processed",
                action=action,
                success=result.get("success", False)
            )

            return result

        except Exception as e:
            logger.error("generation_action_failed", action=action, error=str(e))
            return {
                "success": False,
                "error": f"生成操作失败: {str(e)}",
                "state": self.state_type.value
            }

    async def _format_document(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化工艺文档

        Args:
            parameters: 格式化参数

        Returns:
            格式化结果
        """
        document = self.context.get("document")
        if not document:
            return {"success": False, "error": "没有可格式化的文档"}

        format_options = parameters.get("options", {})
        formatted_doc = document.copy()

        # 应用格式化选项
        if format_options.get("sort_operations", True):
            # 按工序顺序排序
            if "operations" in formatted_doc:
                formatted_doc["operations"].sort(key=lambda x: x.get("sequence", 0))

        if format_options.get("standardize_parameters", True):
            # 标准化参数格式
            if "parameters" in formatted_doc:
                # 这里可以添加参数标准化逻辑
                pass

        if format_options.get("add_timestamps", True):
            # 添加时间戳
            formatted_doc["formatted_at"] = datetime.now().isoformat()
            formatted_doc["formatter"] = "process_document_generator"

        # 更新上下文中的文档
        self.context["formatted_document"] = formatted_doc

        return {
            "success": True,
            "message": "文档格式化完成",
            "formatted_document": formatted_doc,
            "applied_options": format_options
        }

    async def _apply_template(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用文档模板

        Args:
            parameters: 模板参数

        Returns:
            模板应用结果
        """
        document = self.context.get("document") or self.context.get("formatted_document")
        if not document:
            return {"success": False, "error": "没有可应用模板的文档"}

        template_id = parameters.get("template_id", "standard_process_template")
        template_options = parameters.get("options", {})

        # 这里实现具体的模板应用逻辑
        # 暂时返回模拟结果
        templated_doc = {
            "template_applied": True,
            "template_id": template_id,
            "original_document": document,
            "header": self._generate_template_header(document, template_options),
            "content": self._generate_template_content(document, template_options),
            "footer": self._generate_template_footer(document, template_options),
            "applied_at": datetime.now().isoformat()
        }

        self.context["templated_document"] = templated_doc

        return {
            "success": True,
            "message": f"模板 '{template_id}' 应用成功",
            "templated_document": templated_doc
        }

    def _generate_template_header(self, document: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """生成模板头部"""
        return {
            "document_id": document.get("id", "unknown"),
            "document_name": document.get("name", "未命名工艺文件"),
            "template_version": options.get("template_version", "1.0"),
            "generation_date": datetime.now().strftime("%Y-%m-%d"),
            "company_info": options.get("company_info", {})
        }

    def _generate_template_content(self, document: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """生成模板内容"""
        content = {
            "part_info": document.get("part_info", {}),
            "operations": document.get("operations", []),
            "parameters": document.get("parameters", {}),
            "quality_requirements": document.get("quality_requirements", []),
            "additional_sections": options.get("additional_sections", [])
        }
        return content

    def _generate_template_footer(self, document: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """生成模板尾部"""
        return {
            "approval_info": document.get("approval_info", {}),
            "revision_history": document.get("revision_history", []),
            "notes": options.get("footer_notes", ""),
            "page_number": 1,
            "total_pages": 1
        }

    async def _generate_pdf(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成PDF文件

        Args:
            parameters: PDF生成参数

        Returns:
            PDF生成结果
        """
        # 这里实现具体的PDF生成逻辑
        # 暂时返回模拟结果
        document = self.context.get("templated_document") or self.context.get("document")
        if not document:
            return {"success": False, "error": "没有可生成PDF的文档"}

        pdf_file = {
            "id": f"pdf_{datetime.now().timestamp()}",
            "filename": f"{document.get('id', 'process')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "format": "pdf",
            "size_kb": 1024,  # 模拟文件大小
            "generated_at": datetime.now().isoformat(),
            "download_url": f"/api/documents/{document.get('id')}/download/pdf",
            "metadata": {
                "page_count": parameters.get("page_count", 1),
                "quality": parameters.get("quality", "standard"),
                "includes_images": parameters.get("includes_images", False)
            }
        }

        self.generated_files.append(pdf_file)

        return {
            "success": True,
            "message": "PDF文件生成成功",
            "pdf_file": pdf_file
        }

    async def _generate_word(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成Word文档

        Args:
            parameters: Word生成参数

        Returns:
            Word生成结果
        """
        # 这里实现具体的Word生成逻辑
        # 暂时返回模拟结果
        document = self.context.get("templated_document") or self.context.get("document")
        if not document:
            return {"success": False, "error": "没有可生成Word的文档"}

        word_file = {
            "id": f"word_{datetime.now().timestamp()}",
            "filename": f"{document.get('id', 'process')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
            "format": "docx",
            "size_kb": 512,  # 模拟文件大小
            "generated_at": datetime.now().isoformat(),
            "download_url": f"/api/documents/{document.get('id')}/download/word",
            "metadata": {
                "template_used": parameters.get("template", "standard"),
                "includes_tables": True,
                "format_version": "Office 2016+"
            }
        }

        self.generated_files.append(word_file)

        return {
            "success": True,
            "message": "Word文档生成成功",
            "word_file": word_file
        }

    async def _export_to_pdm(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        导出到PDM系统

        Args:
            parameters: 导出参数

        Returns:
            导出结果
        """
        document = self.context.get("document")
        if not document:
            return {"success": False, "error": "没有可导出的文档"}

        # 这里实现具体的PDM导出逻辑
        # 暂时返回模拟结果
        export_result = {
            "success": True,
            "export_id": f"pdm_export_{datetime.now().timestamp()}",
            "document_id": document.get("id"),
            "pdm_system": parameters.get("pdm_system", "default_pdm"),
            "exported_at": datetime.now().isoformat(),
            "exported_files": [f["filename"] for f in self.generated_files],
            "metadata": {
                "export_format": parameters.get("format", "all"),
                "overwrite_existing": parameters.get("overwrite", False),
                "notify_users": parameters.get("notify_users", [])
            }
        }

        return {
            "success": True,
            "message": "文档已成功导出到PDM系统",
            "export_result": export_result
        }

    async def _set_export_formats(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        设置导出格式

        Args:
            parameters: 格式设置参数

        Returns:
            设置结果
        """
        formats = parameters.get("formats", [])
        if not formats:
            return {"success": False, "error": "未指定导出格式"}

        # 验证格式
        valid_formats = ["json", "pdf", "word", "excel", "xml"]
        invalid_formats = [f for f in formats if f not in valid_formats]

        if invalid_formats:
            return {
                "success": False,
                "error": f"不支持的导出格式: {', '.join(invalid_formats)}",
                "valid_formats": valid_formats
            }

        self.export_formats = formats
        self.context["export_formats"] = formats

        return {
            "success": True,
            "message": f"导出格式已设置为: {', '.join(formats)}",
            "formats": formats
        }

    def can_transition_to(self, target_state_type: StateType) -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target_state_type: 目标状态类型

        Returns:
            是否可以转换
        """
        # 生成状态可以转换到完成状态
        allowed_transitions = {StateType.COMPLETION}
        return target_state_type in allowed_transitions

    def get_generation_summary(self) -> Dict[str, Any]:
        """
        获取生成摘要

        Returns:
            生成摘要信息
        """
        return {
            "state_type": self.state_type.value,
            "files_generated": len(self.generated_files),
            "export_formats": self.export_formats,
            "generation_log_count": len(self.generation_log),
            "generation_duration": self._calculate_duration(),
            "file_types": list(set(f["format"] for f in self.generated_files)),
            "total_size_kb": sum(f.get("size_kb", 0) for f in self.generated_files)
        }

    def get_generated_files(self) -> List[Dict[str, Any]]:
        """
        获取已生成的文件列表

        Returns:
            文件列表
        """
        return self.generated_files.copy()