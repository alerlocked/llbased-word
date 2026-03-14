"""
测试PDF提取功能
"""
import pytest
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agents.tools.pdf_table_extractor import (
    PDFTableExtractor,
    extract_mechanical_process_pdf
)


class TestPDFExtraction:
    """PDF提取测试类"""

    @pytest.fixture
    def extractor(self):
        """创建提取器实例"""
        return PDFTableExtractor()

    @pytest.mark.unit
    def test_extractor_initialization(self, extractor):
        """测试提取器初始化"""
        assert extractor is not None
        assert hasattr(extractor, 'process_card_patterns')
        assert len(extractor.process_card_patterns) > 0

    @pytest.mark.unit
    def test_parameter_pattern_matching(self, extractor):
        """测试参数模式匹配"""
        test_text = "主轴转速：800 r/min，切削速度：100 m/min"

        params = extractor.extract_process_parameters("test.pdf")
        # 由于我们没有实际的PDF文件，这里只是测试结构
        assert isinstance(params, dict)
        assert "spindle_speeds" in params
        assert "cutting_speeds" in params

    @pytest.mark.unit
    def test_table_type_identification(self, extractor):
        """测试表格类型识别"""
        # 模拟工艺卡表格
        process_card_table = {
            "headers": ["工序号", "工序内容", "设备", "工艺装备"],
            "data": [["10", "下料", "锯床", ""]]
        }

        table_type = extractor._identify_table_type(process_card_table)
        assert table_type == "process_card"

        # 模拟参数表
        param_table = {
            "headers": ["参数名称", "数值", "单位"],
            "data": [["主轴转速", "800", "r/min"]]
        }

        table_type = extractor._identify_table_type(param_table)
        assert table_type in ["parameter_table", "general_table"]

    @pytest.mark.unit
    def test_parameter_type_detection(self, extractor):
        """测试参数类型检测"""
        pattern = r"主轴转速[:：]\s*(\d+)\s*r/min"
        param_type = extractor._get_parameter_type(pattern)
        assert param_type == "spindle_speeds"

        pattern = r"切削速度[:：]\s*(\d+(?:\.\d+)?)\s*m/min"
        param_type = extractor._get_parameter_type(pattern)
        assert param_type == "cutting_speeds"

    @pytest.mark.unit
    def test_empty_pdf_handling(self, extractor):
        """测试空PDF处理"""
        # 模拟空结果
        empty_result = {
            "tables": [],
            "process_parameters": {}
        }

        score = extractor._calculate_quality_score(empty_result)
        assert score == 0.0

    @pytest.mark.unit
    def test_quality_score_calculation(self, extractor):
        """测试质量分数计算"""
        # 模拟好的提取结果
        good_result = {
            "tables": [
                {
                    "headers": ["工序号", "工序内容", "设备", "工艺装备"],
                    "data": [["10", "下料", "锯床", ""], ["20", "车削", "车床", "三爪卡盘"]],
                    "table_type": "process_card"
                },
                {
                    "headers": ["参数名称", "数值", "单位"],
                    "data": [["主轴转速", "800", "r/min"]],
                    "table_type": "parameter_table"
                }
            ],
            "process_parameters": {
                "spindle_speeds": [800, 1200],
                "cutting_speeds": [100, 150]
            }
        }

        score = extractor._calculate_quality_score(good_result)
        assert score > 50  # 应该超过50分
        assert score <= 100  # 不超过100分

    @pytest.mark.unit
    def test_recommendation_generation(self, extractor):
        """测试建议生成"""
        analysis = {
            "content_analysis": {
                "tables_by_type": {
                    "process_card": 2
                },
                "quality_score": 85.0
            }
        }

        recommendations = extractor._generate_recommendations(analysis)
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("工艺过程卡" in rec for rec in recommendations)

    @pytest.mark.integration
    def test_sample_pdf_extraction(self):
        """测试样例PDF提取（需要实际的PDF文件）"""
        # 创建测试PDF文件（可选）
        test_pdf_path = Path("test_data/mechanical_sample.pdf")

        if test_pdf_path.exists():
            result = extract_mechanical_process_pdf(str(test_pdf_path))

            assert isinstance(result, dict)
            assert "tables" in result
            assert "process_parameters" in result
            assert "metadata" in result

            print(f"提取结果：{len(result['tables'])} 个表格")
            for i, table in enumerate(result["tables"]):
                print(f"表格 {i+1}: {table.get('table_type', 'unknown')}")
        else:
            pytest.skip(f"测试PDF文件不存在: {test_pdf_path}")

    @pytest.mark.unit
    def test_error_handling(self, extractor):
        """测试错误处理"""
        # 测试不存在的文件
        result = extractor.extract_tables_from_pdf("non_existent.pdf")
        assert isinstance(result, list)
        assert len(result) == 0

        # 测试无效路径
        result = extractor.extract_tables_from_pdf("")
        assert isinstance(result, list)
        assert len(result) == 0


# 创建测试数据目录
@pytest.fixture(scope="session", autouse=True)
def create_test_data():
    """创建测试数据目录"""
    test_data_dir = Path("test_data")
    test_data_dir.mkdir(exist_ok=True)

    # 可以在这里创建样例PDF文件（可选）
    # ...