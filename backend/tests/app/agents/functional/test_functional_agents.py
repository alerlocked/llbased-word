"""
Tests for Functional Agents

Validates:
1. WritingAgent functionality
2. ProofreadAgent functionality
3. ReviewAgent functionality
4. Agent registration and creation
"""
import pytest
import asyncio

from app.agents.core import AgentRegistry, ToolRegistry
from app.agents.functional import (
    discover_agents,
    get_agent_registry,
    create_agent,
    list_available_agents,
)


class TestAgentDiscovery:
    """Tests for agent discovery functionality"""

    def test_discover_agents(self):
        """Test that discover_agents returns registered agents"""
        # First ensure agents are discovered
        registered = discover_agents()

        # Should return a list
        assert isinstance(registered, list)

        # Should contain the three main agents
        assert "writing" in registered
        assert "proofread" in registered
        assert "review" in registered

    def test_get_agent_registry(self):
        """Test getting the agent registry"""
        registry = get_agent_registry()

        assert registry is AgentRegistry

        # After calling get_agent_registry, agents should be discovered
        agents = registry.list_agents()
        assert "writing" in agents
        assert "proofread" in agents
        assert "review" in agents

    def test_create_agent(self):
        """Test creating an agent through the helper function"""
        # First discover agents
        discover_agents()

        agent = create_agent("writing", config={"test": True})
        assert agent is not None
        assert agent.config.get("test") is True

    def test_list_available_agents(self):
        """Test listing available agents"""
        agents = list_available_agents()

        assert isinstance(agents, list)
        # Should contain the three main agents
        assert "writing" in agents
        assert "proofread" in agents
        assert "review" in agents


class TestWritingAgent:
    """Tests for WritingAgent"""

    @pytest.mark.asyncio
    async def test_writing_agent_edit_action(self):
        """Test writing agent with edit action"""
        from app.agents.functional.writing_agent import WritingAgent

        agent = WritingAgent(config={})

        result = await agent.process({
            "action": "edit",
            "content": "Test content",
            "target": "paragraph",
            "requirements": "Make it professional"
        })
        assert result["success"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_writing_agent_invalid_action(self):
        """Test writing agent with invalid action"""
        from app.agents.functional.writing_agent import WritingAgent

        agent = WritingAgent(config={})
        result = await agent.process({
            "action": "invalid_action",
            "content": "Test"
        })
        assert result["success"] is False
        assert "error" in result
        assert result["error_code"] == "INVALID_ACTION"

    @pytest.mark.asyncio
    async def test_writing_agent_fill_action(self):
        """Test writing agent with fill action"""
        from app.agents.functional.writing_agent import WritingAgent
        agent = WritingAgent(config={})
        result = await agent.process({
            "action": "fill",
            "target": "table1",
            "fields": ["field1", "field2"]
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_writing_agent_format_action(self):
        """Test writing agent with format action"""
        from app.agents.functional.writing_agent import WritingAgent
        agent = WritingAgent(config={})
        result = await agent.process({
            "action": "format",
            "content": "Test content",
            "format_rules": ["rule1", "rule2"]
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_writing_agent_generate_action(self):
        """Test writing agent with generate action"""
        from app.agents.functional.writing_agent import WritingAgent
        agent = WritingAgent(config={})
        result = await agent.process({
            "action": "generate",
            "requirements": "Generate a process description"
        })
        assert result["success"] is True


class TestProofreadAgent:
    """Tests for ProofreadAgent"""

    @pytest.mark.asyncio
    async def test_proofread_agent_terminology_check(self):
        """Test proofread agent with terminology check"""
        from app.agents.functional.proofread_agent import ProofreadAgent
        agent = ProofreadAgent(config={})
        result = await agent.process({
            "content": "剥线和压接工艺",
            "check_type": "terminology"
        })
        assert result["success"] is True
        assert "results" in result
        assert "terminology" in result["results"]

    @pytest.mark.asyncio
    async def test_proofread_agent_data_check(self):
        """Test proofread agent with data check"""
        from app.agents.functional.proofread_agent import ProofreadAgent
        agent = ProofreadAgent(config={})
        result = await agent.process({
            "content": "长度 100mm, 温度 25C",
            "check_type": "data"
        })
        assert result["success"] is True
        assert "results" in result
        assert "data" in result["results"]

    @pytest.mark.asyncio
    async def test_proofread_agent_format_check(self):
        """Test proofread agent with format check"""
        from app.agents.functional.proofread_agent import ProofreadAgent
        agent = ProofreadAgent(config={})
        result = await agent.process({
            "content": "# Title\n\nParagraph 1\n\nParagraph 2",
            "check_type": "format"
        })
        assert result["success"] is True
        assert "results" in result
        assert "format" in result["results"]

    @pytest.mark.asyncio
    async def test_proofread_agent_all_checks(self):
        """Test proofread agent with all checks"""
        from app.agents.functional.proofread_agent import ProofreadAgent
        agent = ProofreadAgent(config={})
        result = await agent.process({
            "content": "剥线工艺，长度100mm",
            "check_type": "all"
        })
        assert result["success"] is True
        assert "results" in result
        assert "terminology" in result["results"]
        assert "data" in result["results"]
        assert "format" in result["results"]

    @pytest.mark.asyncio
    async def test_proofread_agent_empty_content(self):
        """Test proofread agent with empty content"""
        from app.agents.functional.proofread_agent import ProofreadAgent
        agent = ProofreadAgent(config={})
        result = await agent.process({
            "content": "",
            "check_type": "all"
        })
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_CONTENT"

    @pytest.mark.asyncio
    async def test_proofread_agent_auto_fix(self):
        """Test proofread agent with auto_fix enabled"""
        from app.agents.functional.proofread_agent import ProofreadAgent
        agent = ProofreadAgent(config={"auto_fix": True})
        result = await agent.process({
            "content": "待定的工艺参数",
            "check_type": "data"
        })
        assert result["success"] is True
        # Should have detected the TBD placeholder
        assert result["summary"]["total_issues"] > 0


class TestReviewAgent:
    """Tests for ReviewAgent"""

    @pytest.mark.asyncio
    async def test_review_agent_compliance_check(self):
        """Test review agent with compliance check"""
        from app.agents.functional.review_agent import ReviewAgent
        agent = ReviewAgent(config={})
        result = await agent.process({
            "content": "标准工艺流程",
            "check_type": "compliance",
            "standards": ["enterprise"]
        })
        assert result["success"] is True
        assert "results" in result
        assert "compliance" in result["results"]

    @pytest.mark.asyncio
    async def test_review_agent_rationality_check(self):
        """Test review agent with rationality check"""
        from app.agents.functional.review_agent import ReviewAgent
        agent = ReviewAgent(config={})
        result = await agent.process({
            "content": "装配后进行包装",
            "check_type": "rationality"
        })
        assert result["success"] is True
        assert "results" in result
        assert "rationality" in result["results"]

    @pytest.mark.asyncio
    async def test_review_agent_risk_check(self):
        """Test review agent with risk check"""
        from app.agents.functional.review_agent import ReviewAgent
        agent = ReviewAgent(config={})
        result = await agent.process({
            "content": "注意安全，危险区域",
            "check_type": "risk"
        })
        assert result["success"] is True
        assert "results" in result
        assert "risk" in result["results"]

    @pytest.mark.asyncio
    async def test_review_agent_all_checks(self):
        """Test review agent with all checks"""
        from app.agents.functional.review_agent import ReviewAgent
        agent = ReviewAgent(config={})
        result = await agent.process({
            "content": "装配工艺流程",
            "check_type": "all",
            "standards": ["enterprise", "safety"]
        })
        assert result["success"] is True
        assert "results" in result
        assert "compliance" in result["results"]
        assert "rationality" in result["results"]
        assert "risk" in result["results"]

    @pytest.mark.asyncio
    async def test_review_agent_empty_content(self):
        """Test review agent with empty content"""
        from app.agents.functional.review_agent import ReviewAgent
        agent = ReviewAgent(config={})
        result = await agent.process({
            "content": "",
            "check_type": "all"
        })
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_CONTENT"

    @pytest.mark.asyncio
    async def test_review_agent_detects_critical_risk(self):
        """Test review agent detects critical risk keywords"""
        from app.agents.functional.review_agent import ReviewAgent
        agent = ReviewAgent(config={})
        result = await agent.process({
            "content": "此工序涉及易燃物品",
            "check_type": "risk"
        })
        assert result["success"] is True
        # Should have detected the risk keyword
        risk_result = result["results"]["risk"]
        assert risk_result["risk_level"] == "critical"


class TestBaseAgent:
    """Tests for BaseAgent functionality"""

    def test_agent_get_info(self):
        """Test agent get_info method"""
        from app.agents.functional.writing_agent import WritingAgent

        agent = WritingAgent(config={"test": True})
        info = agent.get_info()
        assert info["name"] == "writing"
        assert "description" in info
        assert "tools" in info

    @pytest.mark.asyncio
    async def test_agent_execute_method(self):
        """Test agent execute method (standard interface)"""
        from app.agents.functional.writing_agent import WritingAgent
        agent = WritingAgent(config={})
        # Execute with dict input
        result = await agent.execute({
            "action": "edit",
            "content": "Test"
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_agent_execute_with_string_input(self):
        """Test agent execute method with string input"""
        from app.agents.functional.writing_agent import WritingAgent
        agent = WritingAgent(config={})
        # Execute with string input
        result = await agent.execute("Test content")
        assert "success" in result

    @pytest.mark.asyncio
    async def test_agent_use_tool_when_not_available(self):
        """Test agent use_tool when tool is not available"""
        from app.agents.functional.writing_agent import WritingAgent
        agent = WritingAgent(config={})
        # Try to use a tool that doesn't exist
        result = await agent.use_tool("nonexistent_tool", "test")
        assert result["success"] is False
        assert result["error_code"] == "TOOL_NOT_FOUND"
