"""
测试工艺文件服务
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import json

from app.services.process_document_service import ProcessDocumentService


class TestProcessDocumentService:
    """工艺文件服务测试类"""

    @pytest.fixture
    def temp_data_dir(self):
        """创建临时数据目录"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # 清理
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def service(self, temp_data_dir):
        """创建工艺文件服务实例"""
        service = ProcessDocumentService(str(temp_data_dir))
        yield service

    @pytest.mark.integration
    def test_service_initialization(self, temp_data_dir, service):
        """测试服务初始化"""
        assert service.data_path == temp_data_dir
        assert service.templates_path.exists()
        assert service.documents_path.exists()
        assert service.parameters_path.exists()

    @pytest.mark.integration
    def test_template_operations(self, service):
        """测试模板操作"""
        # 创建测试模板
        template_data = {
            "name": "测试模板",
            "description": "用于测试的模板",
            "structure": {
                "header": {
                    "part_name": "零件名称",
                    "part_number": "零件图号"
                },
                "operations": {
                    "fields": [
                        {"name": "工序号", "type": "number", "required": True},
                        {"name": "工序内容", "type": "text", "required": True}
                    ]
                }
            }
        }

        # 保存模板
        template_id = "test_template"
        success = service.save_template(template_id, template_data)
        assert success is True

        # 获取模板
        loaded_template = service.get_template(template_id)
        assert loaded_template is not None
        assert loaded_template["name"] == template_data["name"]
        assert loaded_template["description"] == template_data["description"]

        # 列出模板
        templates = service.list_templates()
        assert len(templates) > 0
        assert any(t["template_id"] == template_id for t in templates)

    @pytest.mark.integration
    def test_document_creation(self, service):
        """测试工艺文件创建"""
        # 首先创建模板
        template_data = {
            "name": "测试工艺卡",
            "description": "测试用工艺文件模板",
            "structure": {
                "header": {
                    "part_name": "零件名称",
                    "part_number": "零件图号",
                    "material": "材料"
                },
                "operations": {
                    "fields": [
                        {"name": "工序号", "type": "number", "required": True},
                        {"name": "工序内容", "type": "text", "required": True}
                    ]
                }
            }
        }
        template_id = "test_process_card"
        service.save_template(template_id, template_data)

        # 创建工艺文件
        part_info = {
            "part_name": "测试零件",
            "part_number": "TEST-001",
            "material": "45#钢"
        }

        doc_id = service.create_document(template_id, "测试工艺文件", part_info)
        assert doc_id is not None

        # 验证文档创建
        document = service.get_document(doc_id)
        assert document is not None
        assert document["name"] == "测试工艺文件"
        assert document["template_id"] == template_id
        assert document["part_info"]["part_name"] == "测试零件"

    @pytest.mark.integration
    def test_document_update(self, service):
        """测试工艺文件更新"""
        # 创建模板和文档
        template_data = {
            "name": "测试模板",
            "description": "测试模板",
            "structure": {"header": {"part_name": "零件名称"}}
        }
        template_id = "update_test_template"
        service.save_template(template_id, template_data)

        part_info = {"part_name": "原始零件"}
        doc_id = service.create_document(template_id, "待更新文件", part_info)

        # 更新文档
        updates = {
            "name": "已更新文件",
            "part_info": {"part_name": "更新后的零件"},
            "operations": [{"step": 1, "content": "测试工序"}]
        }

        success = service.update_document(doc_id, updates)
        assert success is True

        # 验证更新
        updated_doc = service.get_document(doc_id)
        assert updated_doc["name"] == "已更新文件"
        assert updated_doc["part_info"]["part_name"] == "更新后的零件"
        assert len(updated_doc["operations"]) == 1

    @pytest.mark.integration
    def test_document_listing(self, service):
        """测试工艺文件列表"""
        # 创建多个文档
        template_data = {
            "name": "测试模板",
            "description": "测试模板",
            "structure": {"header": {"part_name": "零件名称"}}
        }
        template_id = "list_test_template"
        service.save_template(template_id, template_data)

        # 创建多个文档
        doc_ids = []
        for i in range(3):
            part_info = {"part_name": f"零件{i+1}"}
            doc_id = service.create_document(template_id, f"工艺文件{i+1}", part_info)
            doc_ids.append(doc_id)

        # 列出文档
        documents = service.list_documents()
        assert len(documents) >= 3

        # 验证文档信息
        for doc in documents:
            assert "doc_id" in doc
            assert "name" in doc
            assert "template_id" in doc

    @pytest.mark.integration
    def test_ai_suggestions_generation(self, service):
        """测试AI建议生成"""
        # 创建模板和文档
        template_data = {
            "name": "测试模板",
            "description": "测试模板",
            "structure": {"header": {"part_name": "零件名称", "material": "材料"}}
        }
        template_id = "suggestion_test_template"
        service.save_template(template_id, template_data)

        part_info = {"part_name": "测试零件", "material": "45#钢"}
        doc_id = service.create_document(template_id, "建议测试文件", part_info)

        # 生成AI建议
        context = "需要优化加工工艺"
        suggestions = service.generate_ai_suggestions(doc_id, context)

        assert isinstance(suggestions, list)
        # 验证建议结构
        for suggestion in suggestions:
            assert "type" in suggestion
            assert "title" in suggestion
            assert "description" in suggestion
            assert "relevance" in suggestion

    @pytest.mark.integration
    def test_document_export(self, service):
        """测试工艺文件导出"""
        # 创建模板和文档
        template_data = {
            "name": "测试模板",
            "description": "测试模板",
            "structure": {"header": {"part_name": "零件名称"}}
        }
        template_id = "export_test_template"
        service.save_template(template_id, template_data)

        part_info = {"part_name": "测试零件"}
        doc_id = service.create_document(template_id, "导出测试文件", part_info)

        # 导出为Markdown
        export_path = service.export_document(doc_id, "markdown")
        assert export_path is not None

        # 验证导出文件存在
        export_file = Path(export_path)
        assert export_file.exists()

        # 验证导出内容
        with open(export_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "# 导出测试文件" in content
            assert "## 零件信息" in content

    @pytest.mark.integration
    def test_completeness_score_calculation(self, service):
        """测试完整性分数计算"""
        # 创建完整的文档
        complete_doc = {
            "part_info": {
                "part_name": "完整零件",
                "part_number": "PART-001",
                "material": "45#钢"
            },
            "operations": [
                {"step": 1, "content": "工序1"},
                {"step": 2, "content": "工序2"},
                {"step": 3, "content": "工序3"}
            ],
            "parameters": {"spindle_speed": "800r/min"},
            "quality_requirements": ["Ra1.6", "IT7"]
        }

        score = service._calculate_completeness_score(complete_doc)
        assert score > 80  # 应该超过80分

        # 创建不完整的文档
        incomplete_doc = {
            "part_info": {"part_name": "不完整零件"},
            "operations": [],
            "parameters": {},
            "quality_requirements": []
        }

        score = service._calculate_completeness_score(incomplete_doc)
        assert score < 50  # 应该低于50分

    @pytest.mark.integration
    def test_builtin_templates(self, service):
        """测试内置模板"""
        # 检查内置模板是否已创建
        templates = service.list_templates()

        # 应该至少有3个内置模板
        assert len(templates) >= 3

        # 检查特定模板是否存在
        template_names = [t["name"] for t in templates]
        assert "机械加工工艺过程卡" in template_names
        assert "工序卡" in template_names
        assert "检验卡" in template_names

    @pytest.mark.integration
    def test_error_handling(self, service):
        """测试错误处理"""
        # 测试不存在的模板
        result = service.get_template("non_existent_template")
        assert result is None

        # 测试不存在的文档
        result = service.get_document("non_existent_doc")
        assert result is None

        # 测试创建文档使用不存在的模板
        part_info = {"part_name": "测试零件"}
        doc_id = service.create_document("non_existent", "测试文件", part_info)
        assert doc_id is None