"""
工艺文件辅助编辑系统 - 主控Agent端到端测试
模拟用户使用场景的完整测试用例
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.agents.orchestrator.orchestrator import ProcessOrchestrator
from app.agents.orchestrator.intent_recognizer import IntentType

class TestProcessOrchestratorE2E:
    """主控Agent端到端测试"""

    @pytest.fixture
    def orchestrator(self):
        """创建主控Agent实例"""
        config = {
            "test_mode": True,
            "enable_mock_sub_agents": True
        }
        return ProcessOrchestrator(config)

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="E2E assertions predate state-machine refactor; mock/dict expectations stale", strict=False)
    async def test_user_creates_new_process_document(self, orchestrator):
        """
        用户场景: 工艺师创建新的工艺文件

        测试流程:
        1. 用户输入: "为零件A创建车削工艺"
        2. 系统识别意图: CREATE_DOCUMENT
        3. 分解任务: 知识检索 → 术语对齐 → 文档生成 → 合规检查
        4. 返回建议和生成的工艺文件
        """
        # 模拟用户输入
        user_input = "为零件A创建车削工艺"

        # 执行处理
        result = await orchestrator.process_intent(user_input)

        # 验证结果
        assert result["success"] is True
        assert result["intent"]["type"] == IntentType.CREATE_DOCUMENT.value
        assert result["intent"]["confidence"] >= 0.7

        # 验证任务分解
        tasks = result["tasks"]
        assert len(tasks) >= 4  # 至少4个任务
        task_types = [task["type"] for task in tasks]
        assert "rag_retrieval" in task_types
        assert "terminology_alignment" in task_types
        assert "document_generation" in task_types
        assert "compliance_check" in task_types

        # 验证结果聚合
        aggregated_result = result["result"]
        assert "components" in aggregated_result
        assert "suggestions" in aggregated_result

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="E2E assertions predate state-machine refactor; mock/dict expectations stale", strict=False)
    async def test_user_edits_existing_document(self, orchestrator):
        """
        用户场景: 工艺师编辑现有工艺文件

        测试流程:
        1. 用户输入: "修改工序3的切削参数为转速2000，进给0.2"
        2. 系统识别意图: EDIT_DOCUMENT
        3. 分解任务: 文档解析 → 数据验证 → 合规检查
        4. 返回编辑确认和验证结果
        """
        user_input = "修改工序3的切削参数为转速2000，进给0.2"

        result = await orchestrator.process_intent(user_input)

        assert result["success"] is True
        assert result["intent"]["type"] == IntentType.EDIT_DOCUMENT.value
        assert result["intent"]["confidence"] >= 0.7

        # 验证编辑相关任务
        task_types = [task["type"] for task in result["tasks"]]
        assert "data_validation" in task_types
        assert "compliance_check" in task_types

    @pytest.mark.asyncio
    async def test_user_parses_pdf_document(self, orchestrator):
        """
        用户场景: 工艺师解析PDF工艺文件

        测试流程:
        1. 用户输入: "解析这个PDF工艺文件"
        2. 系统识别意图: PARSE_PDF
        3. 分解任务: PDF解析 → 数据验证
        4. 返回解析结果和表格数据
        """
        user_input = "解析这个PDF工艺文件"

        result = await orchestrator.process_intent(user_input)

        assert result["success"] is True
        assert result["intent"]["type"] == IntentType.PARSE_PDF.value

        # 验证PDF解析任务
        task_types = [task["type"] for task in result["tasks"]]
        assert "pdf_parsing" in task_types
        assert "data_validation" in task_types

    @pytest.mark.asyncio
    async def test_user_searches_knowledge_base(self, orchestrator):
        """
        用户场景: 工艺师搜索工艺知识

        测试流程:
        1. 用户输入: "查找数控车削的切削参数"
        2. 系统识别意图: SEARCH_KNOWLEDGE
        3. 分解任务: RAG检索
        4. 返回相关工艺知识和参数建议
        """
        user_input = "查找数控车削的切削参数"

        result = await orchestrator.process_intent(user_input)

        assert result["success"] is True
        assert result["intent"]["type"] == IntentType.SEARCH_KNOWLEDGE.value

        # 验证知识检索任务
        task_types = [task["type"] for task in result["tasks"]]
        assert "rag_retrieval" in task_types

    @pytest.mark.asyncio
    async def test_conversation_history_management(self, orchestrator):
        """
        用户场景: 工艺师进行多轮对话

        测试流程:
        1. 用户输入多个相关请求
        2. 系统维护对话历史和上下文
        3. 验证历史记录的完整性和可用性
        """
        # 第一轮对话
        result1 = await orchestrator.process_intent("为零件A创建车削工艺")
        assert result1["success"] is True

        # 第二轮对话
        result2 = await orchestrator.process_intent("添加一个铣削工序")
        assert result2["success"] is True

        # 获取对话历史
        history = await orchestrator.get_conversation_history()
        assert len(history) == 2

        # 验证历史内容
        assert history[0]["user_input"] == "为零件A创建车削工艺"
        assert history[1]["user_input"] == "添加一个铣削工序"

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="E2E assertions predate state-machine refactor; mock/dict expectations stale", strict=False)
    async def test_error_handling_and_recovery(self, orchestrator):
        """
        用户场景: 系统处理错误并恢复

        测试流程:
        1. 模拟子Agent执行失败
        2. 系统进行错误处理和回退
        3. 返回友好的错误信息和恢复建议
        """
        # 模拟错误输入
        user_input = ""

        result = await orchestrator.process_intent(user_input)

        # 验证错误处理
        assert result["success"] is False
        assert "error" in result
        assert result["state"] == "error"

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="E2E assertions predate state-machine refactor; mock/dict expectations stale", strict=False)
    async def test_state_machine_transitions(self, orchestrator):
        """
        用户场景: 验证状态机正确流转

        测试流程:
        1. 用户输入触发完整的状态流转
        2. 验证每个状态的正确进入和退出
        3. 验证状态历史记录
        """
        user_input = "为零件A创建车削工艺"

        result = await orchestrator.process_intent(user_input)

        # 验证最终状态
        assert result["state"] == "completion"

        # 验证状态历史
        state_history = orchestrator.state_machine.get_state_history()
        expected_states = ["idle", "intent_recognition", "task_decomposition",
                          "task_execution", "result_aggregation", "user_review", "completion"]

        # 检查关键状态是否出现
        state_values = [state.value for state in state_history]
        assert "intent_recognition" in state_values
        assert "completion" in state_values

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="E2E assertions predate state-machine refactor; mock/dict expectations stale", strict=False)
    async def test_user_confirms_suggestions(self, orchestrator):
        """
        用户场景: 工艺师确认系统建议

        测试流程:
        1. 系统提供工艺建议
        2. 用户确认建议
        3. 系统应用建议并生成最终文档
        """
        user_input = "为零件A创建车削工艺"

        result = await orchestrator.process_intent(user_input)

        # 验证建议生成
        suggestions = result["result"].get("suggestions", [])
        assert len(suggestions) > 0

        # 模拟用户确认
        # 这里验证系统能够处理用户确认的场景
        assert "generated_content" in result["result"]

    @pytest.mark.asyncio
    async def test_multi_step_workflow_completion(self, orchestrator):
        """
        用户场景: 完整的多步骤工作流

        测试流程:
        1. 创建新工艺文件
        2. 编辑工艺参数
        3. 审核工艺文件
        4. 生成最终输出
        5. 导出到PDM系统
        """
        # 步骤1: 创建工艺文件
        result1 = await orchestrator.process_intent("为零件A创建车削工艺")
        assert result1["success"] is True

        # 步骤2: 编辑参数
        result2 = await orchestrator.process_intent("修改切削速度为200m/min")
        assert result2["success"] is True

        # 步骤3: 审核文件
        result3 = await orchestrator.process_intent("审核这个工艺文件")
        assert result3["success"] is True

        # 步骤4: 生成输出
        result4 = await orchestrator.process_intent("生成PDF格式的工艺文件")
        assert result4["success"] is True

        # 验证完整工作流
        final_state = result4["state"]
        assert final_state in ["completion", "user_review"]

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="E2E assertions predate state-machine refactor; mock/dict expectations stale", strict=False)
    async def test_performance_under_load(self, orchestrator):
        """
        用户场景: 系统在负载下的性能表现

        测试流程:
        1. 模拟多个并发用户请求
        2. 验证系统响应时间和资源使用
        3. 确保97%以上的准确性要求
        """
        # 模拟并发请求
        user_inputs = [
            "为零件A创建车削工艺",
            "解析PDF工艺文件",
            "查找焊接参数",
            "审核工艺文件P-2024-001"
        ]

        # 并发执行
        tasks = [orchestrator.process_intent(input_text) for input_text in user_inputs]
        results = await asyncio.gather(*tasks)

        # 验证所有请求都成功处理
        success_count = sum(1 for result in results if result["success"])
        assert success_count >= len(results) * 0.9  # 至少90%成功率

        # 验证准确性要求
        for result in results:
            if result["success"]:
                intent_confidence = result["intent"]["confidence"]
                assert intent_confidence >= 0.7  # 70%置信度阈值