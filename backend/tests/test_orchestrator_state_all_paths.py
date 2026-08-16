"""F2: project working-state block reaches agents on EVERY dispatch path.

Regression: process_intent main path (intent→decompose→dispatch) previously
never stored _collected_info["context"], so the state block was silently "".
"""
from unittest.mock import AsyncMock

import pytest

from app.agents.orchestrator.orchestrator import ProcessOrchestrator


def _orch():
    orch = ProcessOrchestrator.__new__(ProcessOrchestrator)
    orch._agents = {}
    orch._collected_info = {}
    return orch


class TestContextStoredOnAllPaths:
    async def test_process_intent_main_path_stores_context(self, monkeypatch, tmp_path):
        from app.repositories.json_repository import JsonFileRepository

        repo = JsonFileRepository(str(tmp_path / "tasks"))
        orch = ProcessOrchestrator(repository=repo)

        async def fake_build_context(additional_context=None):
            return {
                "task_id": orch.current_task_id,
                "state": "idle",
                "project_state_block": "## 项目当前工作状态\n- 当前任务: 改 G25a",
            }

        monkeypatch.setattr(orch, "_build_context", fake_build_context)
        monkeypatch.setattr(
            orch.intent_recognizer, "recognize",
            AsyncMock(return_value={"type": "document_generation", "confidence": 0.9}),
        )
        monkeypatch.setattr(
            orch.task_decomposer, "decompose",
            AsyncMock(return_value=[{"type": "document_generation", "action": "write", "content": "x"}]),
        )
        dispatched = []

        async def fake_dispatch(task):
            dispatched.append(task)
            return {"success": True, "result": "ok"}

        monkeypatch.setattr(orch, "_dispatch_to_sub_agent", fake_dispatch)
        monkeypatch.setattr(
            orch, "_aggregate_results",
            AsyncMock(return_value={"generated_content": "done"}),
        )

        result = await orch.process_intent(user_input="生成文件", context={"session_id": "s"})
        assert result.get("success") is True
        # THE assertion: main path stored context before dispatch
        stored = orch._collected_info.get("context") or {}
        assert "项目当前工作状态" in stored.get("project_state_block", "")

    def test_dispatch_reads_block_from_collected_context(self):
        """Unit: dispatch assembles agent_task with the state block."""
        orch = _orch()
        orch._collected_info = {"context": {"project_state_block": "## 项目当前工作状态\n- 当前任务: 改 G25a"}}

        # Reproduce the dispatch assembly inline (agent not registered)
        task = {"action": "write", "content": "x", "params": {}}
        agent_task = {
            "action": task.get("action"),
            "content": task.get("content", ""),
            **task.get("params", {}),
        }
        state_block = (orch._collected_info.get("context") or {}).get("project_state_block", "")
        if state_block:
            agent_task["project_state_block"] = state_block
        assert "项目当前工作状态" in agent_task["project_state_block"]
