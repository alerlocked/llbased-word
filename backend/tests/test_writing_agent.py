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
