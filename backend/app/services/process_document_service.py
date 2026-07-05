"""
工艺文件服务 - 工艺文件的生成、编辑和管理
"""
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import uuid

from app.shared.logging import get_logger
from app.agents.tools.pdf_table_extractor import extract_mechanical_process_pdf
from app.config import settings

logger = get_logger(__name__)


class ProcessTemplate:
    """工艺文件模板"""

    def __init__(self, template_id: str, name: str, description: str, structure: Dict[str, Any]):
        self.template_id = template_id
        self.name = name
        self.description = description
        self.structure = structure
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at


class ProcessDocument:
    """工艺文件实例"""

    def __init__(self, doc_id: str, template_id: str, name: str, part_info: Dict[str, Any]):
        self.doc_id = doc_id
        self.template_id = template_id
        self.name = name
        self.part_info = part_info
        self.operations = []  # 工序列表
        self.parameters = {}  # 工艺参数
        self.quality_requirements = []  # 质量要求
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.status = "draft"  # draft/review/approved
        self.version = 1


class ProcessDocumentService:
    """
    工艺文件服务

    功能：
    1. 工艺文件模板管理
    2. 工艺文件生成
    3. 工艺文件编辑
    4. AI辅助生成
    5. 工艺参数管理
    """

    def __init__(self, data_path: Optional[str] = None):
        # 使用统一的配置路径
        if data_path is None:
            self.data_path = settings.DATA_DIR / "process_docs"
        else:
            self.data_path = Path(data_path)
        self.templates_path = self.data_path / "templates"
        self.documents_path = self.data_path / "documents"
        self.parameters_path = self.data_path / "parameters"

        # 创建必要的目录
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.templates_path.mkdir(parents=True, exist_ok=True)
        self.documents_path.mkdir(parents=True, exist_ok=True)
        self.parameters_path.mkdir(parents=True, exist_ok=True)

        # 初始化内置模板
        self._init_builtin_templates()

    def _init_builtin_templates(self):
        """初始化内置工艺文件模板"""
        builtin_templates = {
            "machining_process_card": {
                "name": "机械加工工艺过程卡",
                "description": "用于记录零件完整的机械加工工艺过程",
                "structure": {
                    "header": {
                        "part_name": "零件名称",
                        "part_number": "零件图号",
                        "material": "材料",
                        "quantity": "数量",
                        "department": "编制部门",
                        "date": "编制日期"
                    },
                    "operations": {
                        "fields": [
                            {"name": "工序号", "type": "number", "required": True},
                            {"name": "工序内容", "type": "text", "required": True},
                            {"name": "设备", "type": "text", "required": True},
                            {"name": "工艺装备", "type": "text", "required": False},
                            {"name": "切削用量", "type": "text", "required": False},
                            {"name": "工时", "type": "number", "required": False},
                            {"name": "备注", "type": "text", "required": False}
                        ]
                    },
                    "footer": {
                        "prepared_by": "编制",
                        "reviewed_by": "审核",
                        "approved_by": "批准"
                    }
                }
            },
            "operation_card": {
                "name": "工序卡",
                "description": "用于详细描述每道机械加工工序",
                "structure": {
                    "header": {
                        "operation_number": "工序号",
                        "operation_name": "工序名称",
                        "workshop": "车间",
                        "equipment": "设备"
                    },
                    "content": {
                        "drawing": "工序简图",
                        "steps": {
                            "fields": [
                                {"name": "工步号", "type": "number", "required": True},
                                {"name": "工步内容", "type": "text", "required": True},
                                {"name": "刀具", "type": "text", "required": True},
                                {"name": "量具", "type": "text", "required": False},
                                {"name": "切削参数", "type": "object", "required": True}
                            ]
                        },
                        "parameters": {
                            "spindle_speed": "主轴转速(r/min)",
                            "cutting_speed": "切削速度(m/min)",
                            "feed_rate": "进给量(mm/r)",
                            "cutting_depth": "切削深度(mm)"
                        }
                    }
                }
            },
            "inspection_card": {
                "name": "检验卡",
                "description": "用于记录机械加工质量检验要求",
                "structure": {
                    "header": {
                        "inspection_item": "检验项目",
                        "inspection_standard": "检验标准",
                        "inspection_tools": "检验工具"
                    },
                    "items": {
                        "fields": [
                            {"name": "检验序号", "type": "number", "required": True},
                            {"name": "检验内容", "type": "text", "required": True},
                            {"name": "技术要求", "type": "text", "required": True},
                            {"name": "检验方法", "type": "text", "required": True},
                            {"name": "检验结果", "type": "text", "required": False}
                        ]
                    }
                }
            }
        }

        # 保存内置模板
        for template_id, template_data in builtin_templates.items():
            self.save_template(template_id, template_data)

    def save_template(self, template_id: str, template_data: Dict[str, Any]) -> bool:
        """保存工艺文件模板"""
        try:
            template = ProcessTemplate(
                template_id=template_id,
                name=template_data["name"],
                description=template_data["description"],
                structure=template_data["structure"]
            )

            template_path = self.templates_path / f"{template_id}.json"
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "template_id": template.template_id,
                    "name": template.name,
                    "description": template.description,
                    "structure": template.structure,
                    "created_at": template.created_at,
                    "updated_at": template.updated_at
                }, f, ensure_ascii=False, indent=2)

            logger.info("template_saved", template_id=template_id, template_path=str(template_path))
            return True

        except Exception as e:
            logger.exception("template_save_failed", template_id=template_id, error=str(e))
            return False

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取工艺文件模板"""
        try:
            template_path = self.templates_path / f"{template_id}.json"

            if not template_path.exists():
                logger.warning("template_not_found", template_id=template_id)
                return None

            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            logger.info("template_loaded", template_id=template_id)
            return template_data

        except Exception as e:
            logger.exception("template_load_failed", template_id=template_id, error=str(e))
            return None

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有工艺文件模板"""
        try:
            templates = []

            for template_file in self.templates_path.glob("*.json"):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    templates.append(template_data)
                except Exception as e:
                    logger.error("template_load_error", template_file=str(template_file), error=str(e))

            logger.info("templates_listed", count=len(templates))
            return templates

        except Exception as e:
            logger.exception("templates_list_failed", error=str(e))
            return []

    def create_document(self, template_id: str, name: str, part_info: Dict[str, Any]) -> Optional[str]:
        """创建新的工艺文件"""
        try:
            # 获取模板
            template = self.get_template(template_id)
            if not template:
                logger.error("template_not_found_for_document", template_id=template_id)
                return None

            # 创建文档
            doc_id = str(uuid.uuid4())
            document = ProcessDocument(
                doc_id=doc_id,
                template_id=template_id,
                name=name,
                part_info=part_info
            )

            # 根据模板初始化文档内容
            self._initialize_document_from_template(document, template)

            # 保存文档
            doc_path = self.documents_path / f"{doc_id}.json"
            with open(doc_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "doc_id": document.doc_id,
                    "template_id": document.template_id,
                    "name": document.name,
                    "part_info": document.part_info,
                    "operations": document.operations,
                    "parameters": document.parameters,
                    "quality_requirements": document.quality_requirements,
                    "created_at": document.created_at,
                    "updated_at": document.updated_at,
                    "status": document.status,
                    "version": document.version
                }, f, ensure_ascii=False, indent=2)

            # 'name' is a LogRecord reserved attribute; rename to avoid KeyError in StructuredLogger._log
            logger.info("document_created", doc_id=doc_id, doc_name=name, template_id=template_id)
            return doc_id

        except Exception as e:
            logger.exception("document_creation_failed", template_id=template_id, doc_name=name, error=str(e))
            return None

    def _initialize_document_from_template(self, document: ProcessDocument, template: Dict[str, Any]):
        """根据模板初始化文档内容"""
        try:
            template_structure = template.get("structure", {})

            # 初始化零件信息（基于模板结构）
            if "header" in template_structure:
                for field_name, field_label in template_structure["header"].items():
                    if field_name not in document.part_info:
                        document.part_info[field_name] = ""

            # 初始化工序结构
            if "operations" in template_structure and "fields" in template_structure["operations"]:
                # 创建空工序模板
                document.operations = []
                # 可以基于模板创建默认工序

            # 初始化工艺参数
            if "parameters" in template_structure:
                document.parameters = template_structure["parameters"].copy()

            logger.info("document_initialized_from_template", doc_id=document.doc_id, template_id=document.template_id)

        except Exception as e:
            logger.exception("document_initialization_failed", doc_id=document.doc_id, error=str(e))

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取工艺文件"""
        try:
            doc_path = self.documents_path / f"{doc_id}.json"

            if not doc_path.exists():
                logger.warning("document_not_found", doc_id=doc_id)
                return None

            with open(doc_path, 'r', encoding='utf-8') as f:
                document_data = json.load(f)

            logger.info("document_loaded", doc_id=doc_id)
            return document_data

        except Exception as e:
            logger.exception("document_load_failed", doc_id=doc_id, error=str(e))
            return None

    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """更新工艺文件"""
        try:
            # 获取现有文档
            document = self.get_document(doc_id)
            if not document:
                return False

            # 应用更新
            for key, value in updates.items():
                if key in document and key not in ["doc_id", "created_at"]:
                    document[key] = value

            # 更新时间戳
            document["updated_at"] = datetime.now().isoformat()
            document["version"] += 1

            # 保存更新
            doc_path = self.documents_path / f"{doc_id}.json"
            with open(doc_path, 'w', encoding='utf-8') as f:
                json.dump(document, f, ensure_ascii=False, indent=2)

            logger.info("document_updated", doc_id=doc_id, updated_fields=list(updates.keys()))
            return True

        except Exception as e:
            logger.exception("document_update_failed", doc_id=doc_id, error=str(e))
            return False

    def list_documents(self, template_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出工艺文件"""
        try:
            documents = []

            for doc_file in self.documents_path.glob("*.json"):
                try:
                    with open(doc_file, 'r', encoding='utf-8') as f:
                        doc_data = json.load(f)

                    # 应用过滤条件
                    if template_id and doc_data.get("template_id") != template_id:
                        continue
                    if status and doc_data.get("status") != status:
                        continue

                    documents.append({
                        "doc_id": doc_data["doc_id"],
                        "name": doc_data["name"],
                        "template_id": doc_data["template_id"],
                        "status": doc_data["status"],
                        "created_at": doc_data["created_at"],
                        "updated_at": doc_data["updated_at"],
                        "operation_count": len(doc_data.get("operations", [])),
                        "part_name": doc_data.get("part_info", {}).get("part_name", "")
                    })

                except Exception as e:
                    logger.error("document_load_error", doc_file=str(doc_file), error=str(e))

            # 按更新时间排序
            documents.sort(key=lambda x: x["updated_at"], reverse=True)

            logger.info("documents_listed", count=len(documents), template_filter=template_id, status_filter=status)
            return documents

        except Exception as e:
            logger.exception("documents_list_failed", error=str(e))
            return []

    def generate_ai_suggestions(self, doc_id: str, context: str) -> List[Dict[str, Any]]:
        """为工艺文件生成AI建议"""
        try:
            document = self.get_document(doc_id)
            if not document:
                return []

            # 基于上下文生成建议
            suggestions = []

            # 1. 基于零件信息生成工序建议
            part_info = document.get("part_info", {})
            if "material" in part_info:
                material = part_info["material"]
                suggestions.append({
                    "type": "material_process",
                    "title": f"{material} 材料加工工艺建议",
                    "description": f"根据{material}材料的特性，建议使用适当的切削参数和刀具",
                    "relevance": 0.9,
                    "actionable": True
                })

            # 2. 基于上下文生成内容建议
            if "工艺要求" in context:
                suggestions.append({
                    "type": "quality_requirement",
                    "title": "质量要求分析",
                    "description": "建议添加表面粗糙度和尺寸精度的具体要求",
                    "relevance": 0.8,
                    "actionable": True
                })

            # 3. 基于工序数量生成建议
            operations = document.get("operations", [])
            if len(operations) < 3:
                suggestions.append({
                    "type": "operation_completeness",
                    "title": "工序完整性检查",
                    "description": "当前工序较少，建议检查是否遗漏了必要的加工步骤",
                    "relevance": 0.7,
                    "actionable": True
                })

            logger.info("ai_suggestions_generated", doc_id=doc_id, suggestion_count=len(suggestions))
            return suggestions

        except Exception as e:
            logger.exception("ai_suggestions_generation_failed", doc_id=doc_id, error=str(e))
            return []

    def export_document(self, doc_id: str, format_type: str = "pdf") -> Optional[str]:
        """导出工艺文件"""
        try:
            document = self.get_document(doc_id)
            if not document:
                return None

            if format_type == "json":
                # JSON格式直接返回
                export_path = self.documents_path / f"{doc_id}_export.json"
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(document, f, ensure_ascii=False, indent=2)

            elif format_type == "markdown":
                # Markdown格式
                export_path = self.documents_path / f"{doc_id}.md"
                markdown_content = self._convert_to_markdown(document)
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)

            elif format_type == "word":
                # Word格式（需要python-docx）
                # TODO: 实现Word导出
                export_path = self.documents_path / f"{doc_id}.docx"
                # self._convert_to_word(document, export_path)
                return None  # 暂时不支持

            else:
                logger.error("unsupported_export_format", format_type=format_type)
                return None

            logger.info("document_exported", doc_id=doc_id, format_type=format_type, export_path=str(export_path))
            return str(export_path)

        except Exception as e:
            logger.exception("document_export_failed", doc_id=doc_id, format_type=format_type, error=str(e))
            return None

    def _convert_to_markdown(self, document: Dict[str, Any]) -> str:
        """将工艺文件转换为Markdown格式"""
        md_content = f"# {document['name']}\n\n"

        # 零件信息
        md_content += "## 零件信息\n\n"
        for key, value in document.get("part_info", {}).items():
            md_content += f"- **{key}**: {value}\n"
        md_content += "\n"

        # 工序信息
        operations = document.get("operations", [])
        if operations:
            md_content += "## 工序信息\n\n"
            for i, operation in enumerate(operations, 1):
                md_content += f"### 工序 {i}\n\n"
                for key, value in operation.items():
                    md_content += f"- **{key}**: {value}\n"
                md_content += "\n"

        # 工艺参数
        parameters = document.get("parameters", {})
        if parameters:
            md_content += "## 工艺参数\n\n"
            for key, value in parameters.items():
                md_content += f"- **{key}**: {value}\n"
            md_content += "\n"

        # 质量要求
        quality_reqs = document.get("quality_requirements", [])
        if quality_reqs:
            md_content += "## 质量要求\n\n"
            for req in quality_reqs:
                md_content += f"- {req}\n"
            md_content += "\n"

        # 元信息
        md_content += "## 文档信息\n\n"
        md_content += f"- **创建时间**: {document['created_at']}\n"
        md_content += f"- **更新时间**: {document['updated_at']}\n"
        md_content += f"- **状态**: {document['status']}\n"
        md_content += f"- **版本**: {document['version']}\n"

        return md_content


# 全局服务实例
process_document_service = ProcessDocumentService()