"""Unit tests for project-state injection into the main generation chain (N5).

Function-level (no server): _build_llm_messages block injection,
_build_orchestrator_context state loading, _update_project_state / _save_memory
project routing.
"""
import json
from types import SimpleNamespace

import pytest

from app.api import agent as agent_mod


def _request(project_id=None):
    return SimpleNamespace(
        session_id="s-test",
        user_id=1,
        project_id=project_id,
        domain="assembly",
        has_uploaded_file=False,
        uploaded_file_content=None,
        uploaded_file_name=None,
        mode="write",
        generation_mode=None,
        chat_history=[],
        reference_materials=None,
    )


class TestBuildLlmMessagesStateBlock:
    def test_state_block_appended_to_system(self):
        msgs = agent_mod._build_llm_messages(
            system_prompt="base",
            user_input="继续改",
            project_state_block="## 项目当前工作状态（接续上一会话）\n- 当前任务: 改 G25a",
        )
        assert "项目当前工作状态" in msgs[0]["content"]
        assert msgs[0]["role"] == "system"

    def test_no_block_omitted(self):
        msgs = agent_mod._build_llm_messages(system_prompt="base", user_input="hi")
        assert "项目当前工作状态" not in msgs[0]["content"]

    def test_contract_keys_unchanged(self):
        msgs = agent_mod._build_llm_messages(
            system_prompt="base", user_input="hi", chat_history=[{"role": "user", "content": "a"}]
        )
        assert msgs[-1]["role"] == "user"
        assert len([m for m in msgs if m["role"] == "system"]) == 1


class TestBuildOrchestratorContextState:
    def test_state_loaded_when_project_id(self, tmp_path, monkeypatch):
        from app.services.project_state_service import ProjectStateService

        svc = ProjectStateService(tmp_path)
        svc.update_from_turn(5, "prev-session", "继续修改 G25a 工序内容", "edit_document", None)
        monkeypatch.setattr(
            "app.services.project_state_service.project_state_service", svc
        )

        ctx = agent_mod._build_orchestrator_context(
            request=_request(project_id=5), user_input="接着改", mode="write"
        )
        assert "G25a" in ctx["project_state_block"]
        assert "接续上一会话" in ctx["project_state_block"]

    def test_no_project_id_empty_block(self):
        ctx = agent_mod._build_orchestrator_context(
            request=_request(project_id=None), user_input="hi", mode="qa"
        )
        assert ctx["project_state_block"] == ""


class TestUpdateProjectState:
    def test_writes_state_file(self, tmp_path, monkeypatch):
        from app.services.project_state_service import ProjectStateService

        svc = ProjectStateService(tmp_path)
        monkeypatch.setattr(
            "app.services.project_state_service.project_state_service", svc
        )
        agent_mod._update_project_state(9, "s1", "继续改 G25a", "edit_document", ["G25a"])
        state = svc.load(9)
        assert state["last_session_id"] == "s1"
        assert "G25a" in state["focus_chapters"]
        assert state["recent_intents"] == ["edit_document"]

    def test_no_project_id_noop(self, tmp_path, monkeypatch):
        from app.services.project_state_service import ProjectStateService

        svc = ProjectStateService(tmp_path)
        monkeypatch.setattr(
            "app.services.project_state_service.project_state_service", svc
        )
        agent_mod._update_project_state(None, "s1", "hi", None, None)
        assert list(tmp_path.glob("*.json")) == []

    def test_failure_swallowed(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("state service down")

        monkeypatch.setattr(
            "app.services.project_state_service.project_state_service",
            SimpleNamespace(update_from_turn=boom),
        )
        # must not raise
        agent_mod._update_project_state(1, "s", "hi", None, None)


class TestSaveMemoryProjectRouting:
    async def test_project_id_routes_to_project_service(self, monkeypatch):
        from app.services import memory_service as ms_mod

        ms_mod._project_memory_cache.clear()
        saved = {}

        class FakeSvc:
            def save_summary_async(self, session_id, user_input, content):
                saved["args"] = (session_id, user_input, content)

        monkeypatch.setattr(ms_mod, "get_project_memory_service", lambda pid: FakeSvc())
        agent_mod._save_memory("s1", "in", "out", project_id=3)
        assert saved["args"] == ("s1", "in", "out")

    async def test_no_session_returns_early(self):
        # no exception, nothing happens
        agent_mod._save_memory(None, "in", "out", project_id=3)
