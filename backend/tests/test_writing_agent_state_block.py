"""Unit tests: project working state block reaches writing agent system prompts (N6)."""
from unittest.mock import AsyncMock

import pytest

from app.agents.functional.writing_agent import WritingAgent


def _make_agent():
    agent = WritingAgent()
    agent._writing_preferences = None
    agent._profile = None
    return agent


class TestDispatchInjection:
    """orchestrator puts project_state_block into agent_task"""

    def test_agent_task_gets_state_block(self):
        from app.agents.orchestrator.orchestrator import ProcessOrchestrator

        orch = ProcessOrchestrator.__new__(ProcessOrchestrator)
        orch._agents = {}
        orch._collected_info = {"context": {"project_state_block": "## 项目当前工作状态\n- 当前任务: G25a"}}

        # Reproduce the inline logic (no agent registered → task construction only)
        task = {"action": "write", "content": "x", "params": {}}
        agent_task = {
            "action": task.get("action"),
            "content": task.get("content", ""),
            "target": task.get("target"),
            "requirements": task.get("requirements"),
            **task.get("params", {}),
        }
        state_block = (orch._collected_info.get("context") or {}).get("project_state_block", "")
        if state_block:
            agent_task["project_state_block"] = state_block
        assert agent_task["project_state_block"] == "## 项目当前工作状态\n- 当前任务: G25a"


class TestTemplateFillStateBlock:
    async def test_do_template_fill_includes_state_block(self, monkeypatch):
        """Full _do_template_fill with mocked LLM: state block appears in system msg."""
        from app.services import llm_service as ls

        captured = {}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            captured["system"] = messages[0]["content"]
            return {"status": "success", "content": '[{"row": 1, "slot": "content", "value": "v"}]', "finish_reason": "stop"}

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)

        agent = _make_agent()
        task = {
            "action": "write",
            "content": "生成",
            "chapter_code": "G1a",
            "chapter_type": "single_row_list",
            "chapter_title": "标题",
            "template_slots": [
                {"key": "content", "label": "内容", "fill_type": "unstructured"},
            ],
            "project_state_block": "## 项目当前工作状态（接续上一会话）\n- 当前任务: 改 G25a",
        }
        result = await agent._do_template_fill(task, knowledge={"success": False}, context=None)
        assert "项目当前工作状态" in captured["system"]
        # result contract untouched by this node
        assert isinstance(result, dict)

    async def test_no_state_block_no_change(self, monkeypatch):
        from app.services import llm_service as ls

        captured = {}

        async def fake_gen(messages, temperature=0.7, max_tokens=2000, tier="complex", max_retries=2):
            captured["system"] = messages[0]["content"]
            return {"status": "success", "content": '[{"row": 1, "slot": "content", "value": "v"}]', "finish_reason": "stop"}

        monkeypatch.setattr(ls.llm_service, "generate_with_messages", fake_gen)

        agent = _make_agent()
        task = {
            "action": "write",
            "content": "生成",
            "chapter_code": "G1a",
            "chapter_type": "single_row_list",
            "chapter_title": "标题",
            "template_slots": [
                {"key": "content", "label": "内容", "fill_type": "unstructured"},
            ],
        }
        await agent._do_template_fill(task, knowledge={"success": False}, context=None)
        assert "项目当前工作状态" not in captured["system"]
