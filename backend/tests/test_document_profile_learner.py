"""
test_document_profile_learner.py - DocumentProfileLearner unit tests.

Focus: N1 (spec_patterns 扩展) + N2 (triple 携带 process 字段 / _section_at 按位置取工序).
Covers the _extract_triples rule-based path directly (no LLM, no async).
"""
from app.services.document_profile_learner import DocumentProfileLearner


def _learner() -> DocumentProfileLearner:
    return DocumentProfileLearner()


# ---------------------------------------------------------------------------
# spec recognition + process binding (N1 + N2)
# ---------------------------------------------------------------------------

def test_spec_with_process_field_bound_to_section():
    """M5×8 螺栓 + 力矩 → triple subject 含螺栓/M5，且 process == 装配。"""
    learner = _learner()
    content = "1 装配\n用 M5×8 螺栓 2 个拧紧,拧紧力矩为3.6±0.4N·m。"
    triples = learner._extract_triples(content)

    # at least one triple whose subject mentions 螺栓 or M5
    spec_triples = [t for t in triples if ("螺栓" in t["s"]) or ("M5" in t["s"])]
    assert spec_triples, f"no spec triple found in {triples}"
    # every spec-bound triple must carry process == 装配 (the only section)
    for t in spec_triples:
        assert "process" in t, f"triple missing process key: {t}"
        assert t["process"] == "装配", f"expected process=装配, got {t['process']}"


def test_reversed_stud_recognized():
    """反序表述 '螺柱 M5 8' 应被识别为规格 subject。"""
    learner = _learner()
    content = "1 准备\n螺柱 M5 8 A2-70 ... 力矩3.6N·m"
    triples = learner._extract_triples(content)
    spec_triples = [t for t in triples if "螺柱" in t["s"] or "M5" in t["s"]]
    assert spec_triples, f"reversed stud not recognized: {triples}"


def test_m_spec_without_bolt_char_still_matched():
    """M5×8 螺纹规格(不带螺字)应被 M\\d+[-×xX]\\d+ 认。"""
    learner = _learner()
    content = "1 装配\n使用 M6×12 规格紧固,拧紧力矩为45N·m"
    triples = learner._extract_triples(content)
    spec_triples = [t for t in triples if "M6" in t["s"] or "×12" in t["s"]]
    assert spec_triples, f"M-spec without 螺 not matched: {triples}"


# ---------------------------------------------------------------------------
# _section_at (N2) — positional section lookup
# ---------------------------------------------------------------------------

def test_section_at_returns_nearest_preceding_header():
    learner = _learner()
    content = "1 准备\nxx\n2 焊接\nyy"
    headers = learner._collect_headers(content)
    # locate pos of "yy"
    pos_yy = content.index("yy")
    assert learner._section_at(pos_yy, headers) == "焊接"
    # "xx" sits under 准备
    pos_xx = content.index("xx")
    assert learner._section_at(pos_xx, headers) == "准备"


def test_section_at_before_first_header_is_none():
    learner = _learner()
    content = "前言内容\n1 准备\nxx"
    headers = learner._collect_headers(content)
    # a position strictly before the first header → None
    assert learner._section_at(0, headers) is None


def test_section_at_no_headers_returns_none():
    learner = _learner()
    assert learner._section_at(5, []) is None


# ---------------------------------------------------------------------------
# triple shape — process key always present
# ---------------------------------------------------------------------------

def test_triples_carry_process_key():
    learner = _learner()
    triples = learner._extract_triples("1 装配\n用 M5×8 螺栓,拧紧力矩为3.6±0.4N·m。")
    assert triples, "expected at least one triple"
    for t in triples:
        assert "process" in t, f"triple missing process key: {t}"


# ---------------------------------------------------------------------------
# negative cases — must not over-match
# ---------------------------------------------------------------------------

def test_plain_count_not_matched_as_m_spec():
    """'共 58 个零件' 不应被 M\\d+[-×xX]\\d+ 误抽（无 M 前缀 + 无连接符）。"""
    learner = _learner()
    content = "1 装配\n本工序共 58 个零件。"
    triples = learner._extract_triples(content)
    # no triple should treat "58" / "个零件" as a spec subject
    bad = [t for t in triples if "58" in t["s"] or "零件" in t["s"]]
    assert bad == [], f"plain count wrongly matched as spec: {bad}"


def test_m_number_without_connector_or_bolt_not_matched():
    """'M58 个零件' 无螺字且无 -/×/x 连接，不抽为规格。"""
    learner = _learner()
    content = "1 装配\n标注 M58 个零件备用,温度为800°C。"
    triples = learner._extract_triples(content)
    # the only legit triple here is 温度; "M58" alone must NOT become a spec subject
    spec_subjects = [t["s"] for t in triples if "M58" in t["s"]]
    assert spec_subjects == [], f"bare M-number wrongly matched as spec: {spec_subjects}"
    # temperature triple should still be present
    assert any(t["r"] == "温度" for t in triples), f"temperature triple missing: {triples}"
