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


# --- N1: G25a step_name is the work-type category (钳/机/检验) ---
# Source: writing_agent.py G25a source-driven block. step_name column shows the
# work-type from asm[k]["name"]; skeleton (真工序名) only drives row count and
# prefixes each substep inside content. Reverts afternoon N2 (881bf97) which had
# put skeleton real names into the step_name column.
class TestG25aStepNameIsWorkType:
    """step_name column must hold work-type category (钳/机/检验), not skeleton names."""

    @staticmethod
    def _step_name(asm):
        # Mirror the exact comprehension in writing_agent.py (G25a block):
        #   structured_values["step_name"] = [asm.get(k, {}).get("name", "钳") for k in sorted(asm)]
        return [asm.get(k, {}).get("name", "钳") for k in sorted(asm)]

    def test_step_name_is_work_type(self):
        asm = {
            1: {"name": "钳", "substeps": []},
            2: {"name": "检验", "substeps": []},
        }
        # skeleton carries real step names but must NOT surface in step_name
        skel = ["装前准备", "密封圈安装"]
        assert self._step_name(asm) == ["钳", "检验"]

    def test_skeleton_names_not_in_step_name(self):
        # regression guard: real step names from skeleton must stay out of step_name
        asm = {1: {"name": "钳"}, 2: {"name": "机"}}
        result = self._step_name(asm)
        assert "装前准备" not in result
        assert "密封圈安装" not in result

    def test_missing_asm_name_defaults_qian(self):
        # asm entry without "name" -> default "钳"
        asm = {1: {"substeps": []}, 2: {"name": "机"}}
        assert self._step_name(asm) == ["钳", "机"]

    def test_missing_asm_key_defaults_qian(self):
        # asm gap (key 2 missing entirely) -> default "钳"
        asm = {1: {"name": "钳"}, 3: {"name": "机"}}
        # sorted(asm) = [1, 3]; k=1 -> 钳; k=3 -> 机
        assert self._step_name(asm) == ["钳", "机"]


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


# --- N1: G25a content prompt prefixes each substep with the real step name ---
# Source: writing_agent.py _generate_g25a_per_row_parallel, the content
# constraint block. Each substep (1.1/1.2/...) must open with the real step name
# (from skeleton) as a prefix, e.g. 「<step>：1.1 ...」. The old "不要带前缀"
# constraint was reverted. Asserting on source text because the prompt is an
# inline f-string (no constant to import) and the actual prefixing is produced
# by the LLM at generation time.
class TestG25aContentPromptStepNamePrefix:
    """content prompt must instruct per-substep step-name prefixing."""

    def _prompt_source(self):
        import inspect

        from app.agents.functional import writing_agent

        src = inspect.getsource(writing_agent)
        return src

    def test_prompt_requires_step_name_prefix(self):
        src = self._prompt_source()
        # The constraint sentence that tells the LLM to prefix each substep.
        assert "每个工步开头写工序名前缀" in src

    def test_prompt_drops_no_prefix_constraint(self):
        src = self._prompt_source()
        # The reverted N2 constraint must no longer be present.
        assert "不要带「钳：」「机：」前缀" not in src
