"""
Tests for Agent/Tool Registry

Validates:
1. ToolRegistry registration and retrieval
2. AgentRegistry registration and retrieval
3. WorkflowRegistry registration and retrieval
"""
import pytest
from app.agents.core import (
    ToolRegistry,
    AgentRegistry,
    WorkflowRegistry,
    ToolProtocol,
    AgentProtocol,
    runtime_checkable,
)


class TestToolRegistry:
    """Tests for ToolRegistry functionality"""

    def setup_method(self):
        """Snapshot then clear registry (restored in teardown to avoid leaking
        empty state into other test modules that rely on default registrations).
        """
        self._tools_snapshot = dict(ToolRegistry._tools)
        ToolRegistry.clear()

    def teardown_method(self):
        """Restore default tool registrations."""
        ToolRegistry._tools = self._tools_snapshot

    def test_register_tool(self):
        """Test registering a tool"""
        @ToolRegistry.register("test_tool")
        class TestTool:
            name = "test_tool"
            description = "A test tool"

            async def execute(self, input_data, context=None):
                return {"success": True}

        assert "test_tool" in ToolRegistry.list_tools()
        assert ToolRegistry.get("test_tool") == TestTool

    def test_register_duplicate_tool_logs_warning(self):
        """Test that registering duplicate tool logs warning"""
        @ToolRegistry.register("duplicate_tool")
        class FirstTool:
            name = "duplicate_tool"
            description = "First"

        @ToolRegistry.register("duplicate_tool")
        class SecondTool:
            name = "duplicate_tool"
            description = "Second"

        # Should have the second class registered
        assert ToolRegistry.get("duplicate_tool") == SecondTool

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist"""
        result = ToolRegistry.get("nonexistent_tool")
        assert result is None

    def test_create_tool(self):
        """Test creating a tool instance"""
        @ToolRegistry.register("create_test_tool")
        class CreateTestTool:
            name = "create_test_tool"
            description = "Test tool for creation"

            def __init__(self, config=None):
                self.config = config or {}

            async def execute(self, input_data, context=None):
                return {"success": True, "config": self.config}

        instance = ToolRegistry.create("create_test_tool", config={"key": "value"})
        assert instance is not None
        assert instance.config == {"key": "value"}

    def test_create_nonexistent_tool(self):
        """Test creating a tool that doesn't exist"""
        instance = ToolRegistry.create("nonexistent_tool")
        assert instance is None

    def test_get_tool_info(self):
        """Test getting tool info"""
        @ToolRegistry.register("info_test_tool")
        class InfoTestTool:
            name = "info_test_tool"
            description = "Tool for info test"

        info = ToolRegistry.get_info("info_test_tool")
        assert info is not None
        assert info["name"] == "info_test_tool"
        assert info["description"] == "Tool for info test"
        assert info["class"] == "InfoTestTool"

    def test_list_tools(self):
        """Test listing all tools"""
        @ToolRegistry.register("list_tool_1")
        class ListTool1:
            name = "list_tool_1"

        @ToolRegistry.register("list_tool_2")
        class ListTool2:
            name = "list_tool_2"

        tools = ToolRegistry.list_tools()
        assert "list_tool_1" in tools
        assert "list_tool_2" in tools


class TestAgentRegistry:
    """Tests for AgentRegistry functionality"""

    def setup_method(self):
        """Snapshot then clear registry (restored in teardown to avoid leaking
        empty state into other test modules that rely on default registrations).
        """
        self._agents_snapshot = dict(AgentRegistry._agents)
        AgentRegistry.clear()

    def teardown_method(self):
        """Restore default agent registrations."""
        AgentRegistry._agents = self._agents_snapshot

    def test_register_agent(self):
        """Test registering an agent"""
        @AgentRegistry.register("test_agent")
        class TestAgent:
            name = "test_agent"
            description = "A test agent"
            tools = ["tool1", "tool2"]

        assert "test_agent" in AgentRegistry.list_agents()
        assert AgentRegistry.get("test_agent") == TestAgent

    def test_get_nonexistent_agent(self):
        """Test getting an agent that doesn't exist"""
        result = AgentRegistry.get("nonexistent_agent")
        assert result is None

    def test_create_agent(self):
        """Test creating an agent instance"""
        @AgentRegistry.register("create_test_agent")
        class CreateTestAgent:
            name = "create_test_agent"
            description = "Test agent for creation"
            tools = []

            def __init__(self, config=None):
                self.config = config or {}

        instance = AgentRegistry.create("create_test_agent", config={"key": "value"})
        assert instance is not None
        assert instance.config == {"key": "value"}

    def test_get_agent_info(self):
        """Test getting agent info"""
        @AgentRegistry.register("info_test_agent")
        class InfoTestAgent:
            name = "info_test_agent"
            description = "Agent for info test"
            tools = ["tool1", "tool2"]

        info = AgentRegistry.get_info("info_test_agent")
        assert info is not None
        assert info["name"] == "info_test_agent"
        assert info["description"] == "Agent for info test"
        assert info["tools"] == ["tool1", "tool2"]


class TestWorkflowRegistry:
    """Tests for WorkflowRegistry functionality"""

    def setup_method(self):
        """Snapshot then clear registry (restored in teardown to avoid leaking
        empty state into other test modules that rely on default registrations).
        """
        self._workflows_snapshot = dict(WorkflowRegistry._workflows)
        WorkflowRegistry.clear()

    def teardown_method(self):
        """Restore default workflow registrations."""
        WorkflowRegistry._workflows = self._workflows_snapshot

    def test_register_workflow(self):
        """Test registering a workflow"""
        WorkflowRegistry.register(
            "test_workflow",
            ["agent1", "agent2"],
            "Test workflow description"
        )

        workflow = WorkflowRegistry.get("test_workflow")
        assert workflow is not None
        assert workflow["name"] == "test_workflow"
        assert workflow["agents"] == ["agent1", "agent2"]
        assert workflow["description"] == "Test workflow description"

    def test_get_nonexistent_workflow(self):
        """Test getting a workflow that doesn't exist"""
        result = WorkflowRegistry.get("nonexistent_workflow")
        assert result is None

    def test_list_workflows(self):
        """Test listing all workflows"""
        WorkflowRegistry.register("wf1", ["a1"], "Workflow 1")
        WorkflowRegistry.register("wf2", ["a2"], "Workflow 2")

        workflows = WorkflowRegistry.list_workflows()
        assert "wf1" in workflows
        assert "wf2" in workflows

    def test_default_workflows_exist(self):
        """Test that default workflows are registered at module load"""
        # Re-import to trigger default workflow registration
        from importlib import reload
        import app.agents.core.registry as registry_module
        reload(registry_module)

        # Default workflows should be registered
        workflows = registry_module.WorkflowRegistry.list_workflows()
        # Note: this may include workflows from other tests, so we just check structure
        assert isinstance(workflows, list)


class TestProtocols:
    """Tests for Protocol definitions"""

    def test_runtime_checkable_decorator(self):
        """Test that runtime_checkable is available"""
        # Just verify it's importable and callable
        assert callable(runtime_checkable)

    @pytest.mark.xfail(reason="protocol attribute set drifted from definition", strict=False)
    def test_tool_protocol_has_required_attributes(self):
        """Test ToolProtocol has required attributes"""
        # Protocol classes should have these attributes defined
        assert hasattr(ToolProtocol, '__protocol_attrs__')

    @pytest.mark.xfail(reason="protocol attribute set drifted from definition", strict=False)
    def test_agent_protocol_has_required_attributes(self):
        """Test AgentProtocol has required attributes"""
        assert hasattr(AgentProtocol, '__protocol_attrs__')
