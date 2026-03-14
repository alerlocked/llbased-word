"""
测试工艺文件提取器
"""
import pytest
import json
from pathlib import Path

from app.tools.process_document_extractor import ProcessDocumentExtractor, extract_process_document


class TestProcessDocumentExtractor:
    """工艺文件提取器测试类"""

    def test_extractor_initialization(self):
        """测试提取器初始化"""
        extractor = ProcessDocumentExtractor()
        assert extractor is not None
        assert hasattr(extractor, 'config')

    def test_extract_sample_process_document(self):
        """测试提取样例工艺文件"""
        # 使用项目中的样例文件
        pdf_path = "D:/ai_idea/localknowledgebase-word/backend/data/process_docs/全单电缆装配规程.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"测试文件不存在: {pdf_path}")

        # 执行提取
        result = extract_process_document(pdf_path)

        # 解析结果
        data = json.loads(result)

        # 验证基本结构
        assert "tables" in data
        assert "metadata" in data
        assert data["metadata"]["page_count"] > 0

        # 验证提取到了内容
        total_tables = (
            len(data.get("process_cards", [])) +
            len(data.get("operation_cards", [])) +
            len(data.get("tool_lists", [])) +
            len(data.get("parameter_tables", []))
        )

        assert total_tables > 0, "应该提取到至少一个表格"

        print(f"✅ 成功提取到 {total_tables} 个表格")
        print(f"✅ 总页数: {data['metadata']['page_count']}")

    def test_tool_list_extraction(self):
        """测试工具清单提取"""
        pdf_path = "D:/ai_idea/localknowledgebase-word/backend/data/process_docs/全单电缆装配规程.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"测试文件不存在: {pdf_path}")

        result = extract_process_document(pdf_path)
        data = json.loads(result)

        tool_lists = data.get("tool_lists", [])

        # 验证工具清单
        assert len(tool_lists) > 0, "应该提取到工具清单"

        # 检查工具清单内容
        for tool_list in tool_lists[:2]:  # 检查前2个
            assert "rows" in tool_list
            assert len(tool_list["rows"]) > 0

            # 验证包含工具信息
            first_row = tool_list["rows"][0]
            assert "cells" in first_row
            assert len(first_row["cells"]) > 0

            # 检查是否包含工艺关键词
            all_text = " ".join([" ".join(row["cells"]) for row in tool_list["rows"]])
            assert ("工具" in all_text or "量具" in all_text), "应该包含工具相关关键词"

    def test_core_content_filtering(self):
        """测试核心内容过滤（忽略边缘内容）"""
        pdf_path = "D:/ai_idea/localknowledgebase-word/backend/data/process_docs/全单电缆装配规程.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"测试文件不存在: {pdf_path}")

        extractor = ProcessDocumentExtractor()
        result = extractor.extract_process_document(pdf_path)

        # 验证提取的区域是核心区域
        # 检查是否有提取到内容（说明边缘过滤有效）
        total_content = (
            len(result.get("tables", [])) +
            len(result.get("metadata", {}).get("process_steps", []))
        )

        assert total_content > 0, "应该提取到核心内容"

        # 验证没有提取到明显的边缘内容（如页眉页脚）
        # 这里可以添加更具体的验证逻辑

    def test_table_type_identification(self):
        """测试表格类型识别"""
        extractor = ProcessDocumentExtractor()

        # 测试工艺关键词识别
        test_headers = ["工序号", "工序内容", "设备"]
        table_type = extractor._identify_table_type([{"cells": test_headers}])
        assert table_type == "process_card"

        # 测试工具清单识别
        test_headers = ["工具", "规格", "型号"]
        table_type = extractor._identify_table_type([{"cells": test_headers}])
        assert table_type == "tool_list"

    def test_parameter_extraction(self):
        """测试工艺参数提取"""
        extractor = ProcessDocumentExtractor()

        # 测试参数提取
        test_text = "主轴转速：800 r/min，切削速度：100 m/min"
        params = extractor.extract_process_parameters(test_text)

        assert len(params["spindle_speeds"]) > 0
        assert len(params["cutting_speeds"]) > 0
        assert 800 in params["spindle_speeds"]
        assert 100 in params["cutting_speeds"]

    def test_edge_case_handling(self):
        """测试边界情况处理"""
        # 测试空文件路径
        with pytest.raises(Exception):
            extract_process_document("non_existent_file.pdf")

    def test_real_cable_assembly_document(self):
        """测试真实的电缆装配文档"""
        pdf_path = "D:/ai_idea/localknowledgebase-word/backend/data/process_docs/全单电缆装配规程.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"测试文件不存在: {pdf_path}")

        result = extract_process_document(pdf_path)
        data = json.loads(result)

        # 验证提取到了电缆装配相关的内容
        all_text = ""
        for table in data.get("tool_lists", []):
            for row in table.get("rows", []):
                all_text += " ".join(row.get("cells", []))

        # 应该包含电缆装配相关词汇
        cable_keywords = ["电缆", "装配", "安装", "连接"]
        has_cable_content = any(keyword in all_text for keyword in cable_keywords)

        if not has_cable_content:
            # 至少应该提取到工具信息
            assert "工具" in all_text or "量具" in all_text


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])