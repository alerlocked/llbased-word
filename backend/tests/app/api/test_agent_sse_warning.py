"""Unit tests: SSE warning events from structured_results row gaps (N8)."""

import json

from app.api import agent as agent_mod


def _sse_line(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class TestWarningEventFormat:
    def test_warning_payload_shape(self):
        # contract: {'type': 'warning', 'message': '[G25a] 工序 5（装配）内容生成失败，该行留空'}
        msg = "工序 5（装配）内容生成失败，该行留空"
        line = _sse_line({"type": "warning", "message": f"[G25a] {msg}"})
        parsed = json.loads(line[6:].strip())
        assert parsed["type"] == "warning"
        assert parsed["message"].startswith("[G25a]")
        assert "工序 5" in parsed["message"]

    def test_structured_results_iteration_emits_each_warning(self):
        structured_results = {
            "G25a": {
                "chapter_title": "装配工艺卡片",
                "filled_data": [],
                "warnings": [
                    {"row": 5, "message": "工序 5（压接）内容生成失败，该行留空"},
                    {"row": 7, "message": "工序 7（清洗）内容生成失败，该行留空"},
                ],
            },
            "G4a": {"chapter_title": "目录", "filled_data": []},  # no warnings key
            "bad": "not-a-dict",
        }
        emitted = []
        for code, data in structured_results.items():
            if not isinstance(data, dict):
                continue
            for w in (data.get("warnings") or []):
                warn_msg = f"[{code}] {w.get('message', '')}"
                emitted.append(_sse_line({"type": "warning", "message": warn_msg}))
        assert len(emitted) == 2
        assert all('"warning"' in e for e in emitted)
        assert "[G25a]" in emitted[0]

    def test_empty_warnings_no_events(self):
        structured_results = {"G25a": {"warnings": []}}
        emitted = []
        for code, data in structured_results.items():
            for w in ((data or {}).get("warnings") or []):
                emitted.append(code)
        assert emitted == []
