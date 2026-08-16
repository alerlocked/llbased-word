"""Unit tests for ProjectStateService (tmp_path isolated)."""
import json
import threading

import pytest

from app.services.project_state_service import ProjectStateService


@pytest.fixture
def svc(tmp_path):
    return ProjectStateService(tmp_path / "project_state")


class TestLoadUpdate:
    def test_load_missing_returns_empty(self, svc):
        assert svc.load(1) == {}

    def test_update_persists_and_load_roundtrips(self, svc):
        assert svc.update(1, current_task="改 G25a 装配卡") is True
        state = svc.load(1)
        assert state["current_task"] == "改 G25a 装配卡"
        assert state["project_id"] == 1
        assert "updated_at" in state

    def test_corrupt_file_returns_empty_not_raise(self, svc):
        svc._path(2).write_text("{broken json", encoding="utf-8")
        assert svc.load(2) == {}

    def test_rolling_caps_enforced(self, svc):
        svc.update(1, current_task="x" * 500)
        assert len(svc.load(1)["current_task"]) == 200  # STATE_TASK_MAX_CHARS
        svc.update(1, recent_intents=[f"i{n}" for n in range(10)])
        assert len(svc.load(1)["recent_intents"]) == 5  # keep last 5
        svc.update(1, focus_chapters=[f"G{n}a" for n in range(10)])
        assert len(svc.load(1)["focus_chapters"]) == 5

    def test_no_tmp_left_after_write(self, svc):
        svc.update(1, current_task="t")
        assert not list(svc.state_dir.glob("*.tmp"))

    def test_concurrent_updates_no_corrupt(self, svc):
        results = []

        def writer(n):
            results.append(svc.update(1, current_task=f"task-{n}"))

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(results)
        state = svc.load(1)  # parses = not corrupted
        assert state["current_task"].startswith("task-")


class TestUpdateFromTurn:
    def test_extracts_chapter_codes_from_input(self, svc):
        svc.update_from_turn(1, "s1", "继续改 G25a 表格的工序五", "edit_document", None)
        state = svc.load(1)
        assert "G25a" in state["focus_chapters"]
        assert state["last_session_id"] == "s1"
        assert state["recent_intents"] == ["edit_document"]

    def test_extracts_chapter_codes_cjk_adjacent(self, svc):
        # \b never fires between CJK and ASCII; lookarounds must (F1 fix)
        svc.update_from_turn(1, "s1", "修改G25a第3行的内容", None, None)
        assert svc.load(1)["focus_chapters"] == ["G25a"]

    def test_letter_wrapped_codes_not_matched(self, svc):
        svc.update_from_turn(1, "s1", "AG25a型号和RGB25色不是章节", None, None)
        assert svc.load(1)["focus_chapters"] == []

    def test_focus_chapters_dedupe(self, svc):
        svc.update_from_turn(1, "s1", "改 G25a", None, ["G25a"])
        assert svc.load(1)["focus_chapters"] == ["G25a"]

    def test_preference_signal_captured(self, svc):
        svc.update_from_turn(1, "s1", "以后都用力矩单位 N·m 统一写法", None, None)
        assert "以后都" in svc.load(1)["user_preferences"]

    def test_no_preference_signal_not_captured(self, svc):
        svc.update_from_turn(1, "s1", "生成装配工序卡", None, None)
        assert "user_preferences" not in svc.load(1) or not svc.load(1).get("user_preferences")


class TestRenderContextBlock:
    def test_empty_state_renders_empty(self, svc):
        assert svc.render_context_block({}) == ""

    def test_full_state_renders_block(self, svc):
        svc.update_from_turn(1, "s1", "继续修改 G25a 工序内容", "edit_document", None)
        block = svc.render_context_block(svc.load(1))
        assert block.startswith("## 项目当前工作状态")
        assert "G25a" in block
        assert "edit_document" in block


class TestLastOutputSnapshot:
    """N3 (review-pipeline): last_output snapshot + render into state block."""

    def test_output_summary_persisted(self, svc):
        svc.update_from_turn(
            1, "s1", "补齐", "generate",
            output_summary={
                "chapters": [
                    {"code": "G25a", "title": "装配工艺卡片", "rows": 10},
                    {"code": "G4a", "title": "工艺文件目录", "rows": 8},
                ],
                "warnings_count": 2,
            },
        )
        state = svc.load(1)
        lo = state["last_output"]
        assert len(lo["chapters"]) == 2
        assert lo["warnings_count"] == 2
        assert lo["chapters"][0]["code"] == "G25a"
        assert "updated_at" in lo

    def test_no_summary_keeps_old_snapshot(self, svc):
        svc.update_from_turn(1, "s1", "补齐", None, output_summary={"chapters": [{"code": "G4a", "title": "", "rows": 1}], "warnings_count": 0})
        svc.update_from_turn(1, "s1", "继续问", "review_document")  # no summary
        assert svc.load(1)["last_output"]["chapters"][0]["code"] == "G4a"  # not wiped

    def test_rendered_into_context_block(self, svc):
        svc.update_from_turn(
            1, "s1", "补齐", "generate",
            output_summary={"chapters": [{"code": c, "title": "", "rows": 1} for c in ["G4a", "G25a", "G18a"]], "warnings_count": 3},
        )
        block = svc.render_context_block(svc.load(1))
        assert "最近产出" in block
        assert "G25a" in block
        assert "3 处警告" in block
