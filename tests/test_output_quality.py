"""
Unit tests for output quality checks.

Covers:
- ReviewAgent._check_output_quality (duplicate titles, meta-commentary, step ordering)
- WritingAgent._quick_check_output (placeholders, bare numbers, vague language)
- Orchestrator _strip_duplicate_heading
"""
import pytest
from app.agents.functional.review_agent import ReviewAgent
from app.agents.functional.writing_agent import WritingAgent
from app.agents.orchestrator.orchestrator import _strip_duplicate_heading


# ---------------------------------------------------------------------------
# ReviewAgent._check_output_quality
# ---------------------------------------------------------------------------
class TestOutputQualityCheck:
    """Tests for ReviewAgent._check_output_quality."""

    def setup_method(self):
        self.agent = ReviewAgent()

    # --- duplicate titles ---

    def test_no_duplicate_titles_passes(self):
        content = "## 工艺文件目录\n内容\n\n## 引借用文件目录\n内容\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is True
        assert result["warnings"] == []

    def test_duplicate_title_detected(self):
        content = "## 引借用文件目录\n内容\n\n## 引借用文件目录\n内容\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False
        assert any("重复" in w["message"] for w in result["warnings"])

    def test_duplicate_h3_title_detected(self):
        content = "### 装配工艺卡片\n内容\n\n### 装配工艺卡片\n更多内容\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False

    # --- AI meta-commentary ---

    def test_clean_content_passes(self):
        content = "## 工序1：电缆下料\n1.1 按图纸要求截取电缆\n1.2 剥离绝缘层\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is True

    def test_page_reference_detected(self):
        content = "第19页起（1.1 装配前的产品完整性检查）\n工序1内容\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False
        assert any("元描述" in w["message"] for w in result["warnings"])

    def test_original_commentary_detected(self):
        content = "原文中存在型号异常项（如\"6200mmmm\"疑似笔误）\n内容\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False

    def test_ai_preamble_detected(self):
        content = "以下为严格依据知识库原文第15–18页内容整理的工艺文件输出\n## 工序1\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False

    def test_self_evaluation_detected(self):
        content = "格式清晰、层级明确\n## 工序1\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False

    # --- process step ordering ---

    def test_sequential_steps_passes(self):
        content = "工序1 电缆下料\n工序2 安装密封圈\n工序3 行程开关\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is True

    def test_step_gap_detected(self):
        content = "工序3 钳\n工序7 钳\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False
        assert any("不连续" in w["message"] for w in result["warnings"])

    def test_single_step_no_gap_check(self):
        content = "工序1 电缆下料\n1.1 截取电缆\n"
        result = self.agent._check_output_quality(content)
        # Single step can't have gaps — should pass
        assert result["passed"] is True

    def test_consecutive_steps_passes(self):
        content = "工序1 准备\n工序2 下料\n工序3 装配\n工序4 检查\n工序5 包装\n"
        result = self.agent._check_output_quality(content)
        assert result["passed"] is True

    # --- combined ---

    def test_multiple_issues_all_reported(self):
        content = (
            "以下为严格依据知识库原文整理的输出\n"
            "## 引借用文件目录\n内容\n"
            "## 引借用文件目录\n重复内容\n"
            "工序3 装配\n"
            "工序7 测试\n"
        )
        result = self.agent._check_output_quality(content)
        assert result["passed"] is False
        assert len(result["warnings"]) >= 3  # duplicate + meta + gap


# ---------------------------------------------------------------------------
# WritingAgent._quick_check_output
# ---------------------------------------------------------------------------
class TestQuickCheckOutput:
    """Tests for WritingAgent._quick_check_output."""

    def setup_method(self):
        self.agent = WritingAgent()

    def test_clean_content_passes(self):
        content = "## 工序1\n1.1 截取电缆 φ8mm\n检验：1) 尺寸检查\n"
        warnings = self.agent._quick_check_output(content)
        assert warnings == []

    def test_placeholder_detected(self):
        content = "参数[待补充]\n"
        warnings = self.agent._quick_check_output(content)
        assert any("占位符" in w for w in warnings)

    def test_bare_decimal_number_detected(self):
        content = "长度3.5\n温度25.0±0.5\n压力1.2\n"
        warnings = self.agent._quick_check_output(content)
        assert any("无单位" in w for w in warnings)

    def test_vague_language_detected(self):
        content = "适当调整螺栓力度，根据实际情况确定\n"
        warnings = self.agent._quick_check_output(content)
        assert any("模糊" in w for w in warnings)

    def test_number_with_unit_passes(self):
        content = "长度 3.5mm，力矩 3.6±0.4 N·m，温度 25°C\n"
        warnings = self.agent._quick_check_output(content)
        assert warnings == []


# ---------------------------------------------------------------------------
# _strip_duplicate_heading
# ---------------------------------------------------------------------------
class TestStripDuplicateHeading:
    """Tests for orchestrator _strip_duplicate_heading."""

    def test_h3_stripped_when_matching(self):
        content = "### 工艺文件目录\n表格内容\n"
        result = _strip_duplicate_heading(content, "工艺文件目录")
        assert result.startswith("表格内容")

    def test_h2_stripped_when_matching(self):
        content = "## 装配工艺卡片\n工序1内容\n"
        result = _strip_duplicate_heading(content, "装配工艺卡片")
        assert result.startswith("工序1内容")

    def test_non_matching_heading_kept(self):
        content = "## 其他标题\n内容\n"
        result = _strip_duplicate_heading(content, "装配工艺卡片")
        assert "## 其他标题" in result

    def test_leading_whitespace_handled(self):
        content = "\n\n## 工艺文件目录\n内容\n"
        result = _strip_duplicate_heading(content, "工艺文件目录")
        assert result.startswith("内容")

    def test_no_heading_kept(self):
        content = "直接从内容开始\n没有标题\n"
        result = _strip_duplicate_heading(content, "任何标题")
        assert "直接从内容开始" in result
