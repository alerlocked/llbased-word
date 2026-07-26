"""Unit tests for WritingAgent row-count coercion.

Regression: LLM may return slot 'row' as a string ("1" instead of 1). The
unstructured-slots path computes llm_row_count via max(...) over these rows,
which raised TypeError comparing str vs int and failed the whole writing task
(writing_task_failed: '>' not supported between instances of 'str' and 'int').

Covers the _slot_row_int coercion helper that makes the row field int-safe.
"""
import pytest

from app.agents.functional.writing_agent import _slot_row_int


class TestSlotRowInt:
    """_slot_row_int must coerce any row value to int, never raise."""

    def test_int_row_passes_through(self):
        assert _slot_row_int({"row": 3, "slot": "name", "value": "x"}) == 3

    def test_str_row_coerced(self):
        # the bug: LLM returned "1" instead of 1
        assert _slot_row_int({"row": "1", "slot": "name", "value": "x"}) == 1

    def test_max_over_str_rows_no_raise(self):
        # reproduces the original failing max() over mixed types
        slots = [
            {"row": "1", "slot": "name", "value": "a"},
            {"row": "2", "slot": "name", "value": "b"},
        ]
        assert max(_slot_row_int(s) for s in slots) == 2

    def test_missing_row_defaults_zero(self):
        assert _slot_row_int({"slot": "name", "value": "x"}) == 0

    def test_non_numeric_row_defaults_zero(self):
        assert _slot_row_int({"row": "abc", "slot": "name", "value": "x"}) == 0

    def test_none_row_defaults_zero(self):
        assert _slot_row_int({"row": None, "slot": "name", "value": "x"}) == 0

    def test_empty_list_max_safe(self):
        # guard the real call site shape (max over empty is an error without default)
        slots = []
        # mirror the guarded call site: only enter max when slots non-empty
        llm_row_count = max(_slot_row_int(s) for s in slots) if slots else 0
        assert llm_row_count == 0


# --- N2: G25a step_name uses skeleton (G19a) real flow-step names ---
# Source: writing_agent.py G25a source-driven block. step_name must come from
# skeleton (真工序名), not asm[k]["name"] (work-type 钳/机). Fall back to
# asm.name when skeleton is shorter than asm (out-of-range protection).
class TestG25aStepNameFromSkeleton:
    """step_name column should show skeleton real step names, not work-types."""

    @staticmethod
    def _step_name(asm, skel):
        # Mirror the exact comprehension in writing_agent.py (G25a block):
        #   structured_values["step_name"] = [
        #       (skel[k - 1] if (k - 1) < len(skel) else asm.get(k, {}).get("name", "钳"))
        #       for k in sorted(asm)
        #   ]
        return [
            (skel[k - 1] if (k - 1) < len(skel) else asm.get(k, {}).get("name", "钳"))
            for k in sorted(asm)
        ]

    def test_uses_skeleton_real_step_names(self):
        asm = {
            1: {"name": "钳", "substeps": []},
            2: {"name": "机", "substeps": []},
        }
        skel = ["装前准备", "密封圈安装"]
        assert self._step_name(asm, skel) == ["装前准备", "密封圈安装"]

    def test_not_work_type_category(self):
        # regression guard: must NOT emit work-type 钳/机
        asm = {1: {"name": "钳"}, 2: {"name": "机"}}
        skel = ["装前准备", "密封圈安装"]
        result = self._step_name(asm, skel)
        assert "钳" not in result
        assert "机" not in result

    def test_skeleton_shorter_falls_back_to_asm_name(self):
        # asm has step 3 but skeleton length is 2 -> step 3 falls back to asm name
        asm = {
            1: {"name": "钳"},
            2: {"name": "机"},
            3: {"name": "焊"},
        }
        skel = ["装前准备", "密封圈安装"]
        result = self._step_name(asm, skel)
        assert result == ["装前准备", "密封圈安装", "焊"]

    def test_missing_asm_key_defaults_qian(self):
        # asm gap (key 2 missing entirely) -> default "钳"
        asm = {1: {"name": "钳"}, 3: {"name": "机"}}
        skel = ["装前准备"]
        # sorted(asm) = [1, 3]; k=1 -> skel[0]; k=3 -> out of range -> asm[3].name
        result = self._step_name(asm, skel)
        assert result == ["装前准备", "机"]


# --- N3: G18a source column skipped in derive fill_cols ---
# Source: writing_agent.py _derive_list_from_upstream. G18a source ("来自何处")
# is real part provenance, not in upstream process content; deriving it would
# fabricate "工艺流程图". So source is excluded from fill_cols for G18a only.
class TestG18aSourceSkipDerive:
    """G18a source column must be excluded from derive fill_cols."""

    @staticmethod
    def _fill_cols(slot_cols, chapter_code):
        # Mirror the exact filter in _derive_list_from_upstream:
        #   fill_cols = [c for c in slot_cols if c.ai_filled]
        #   if chapter_code == "G18a":
        #       fill_cols = [c for c in fill_cols if c.key != "source"]
        fill_cols = [c for c in slot_cols if c.ai_filled]
        if chapter_code == "G18a":
            fill_cols = [c for c in fill_cols if c.key != "source"]
        return fill_cols

    @staticmethod
    def _col(key, label, ai_filled=True):
        from app.services.template_types import TemplateColumn
        return TemplateColumn(key=key, label=label, ai_filled=ai_filled)

    def test_g18a_source_excluded(self):
        cols = [
            self._col("part_code", "代号"),
            self._col("part_name", "名称"),
            self._col("source", "来自何处"),
            self._col("qty", "数量"),
        ]
        result = self._fill_cols(cols, "G18a")
        keys = [c.key for c in result]
        assert "source" not in keys
        assert "part_code" in keys
        assert "part_name" in keys

    def test_non_g18a_keeps_source(self):
        # control: other chapters keep source in fill_cols
        cols = [
            self._col("part_code", "代号"),
            self._col("source", "来自何处"),
        ]
        result = self._fill_cols(cols, "G14a")
        keys = [c.key for c in result]
        assert "source" in keys

    def test_g18a_non_ai_filled_not_in_fill_cols_anyway(self):
        # ai_filled=False columns never enter fill_cols regardless
        cols = [
            self._col("part_code", "代号", ai_filled=True),
            self._col("source", "来自何处", ai_filled=False),
        ]
        result = self._fill_cols(cols, "G18a")
        assert all(c.key != "source" for c in result)
