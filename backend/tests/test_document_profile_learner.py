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


# ---------------------------------------------------------------------------
# N2' — _extract_triples_from_substeps (process = G19a skeleton 真工序名)
# ---------------------------------------------------------------------------

def test_substeps_process_uses_skeleton_name():
    """step1 process==装配前准备、step2 process==密封圈安装；绝不用 asm[k]['name'](钳)。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [{"content": "用 M5×8 螺栓拧紧,拧紧力矩为3.6±0.4N·m"}]},
        2: {"name": "钳", "substeps": [{"content": "安装密封圈2,力矩1.9N·m"}]},
    }
    skeleton = ["装配前准备", "密封圈安装"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)

    step1 = [t for t in triples if t["process"] == "装配前准备"]
    step2 = [t for t in triples if t["process"] == "密封圈安装"]
    assert step1, f"step1 triples missing: {triples}"
    assert step2, f"step2 triples missing: {triples}"
    # subject 含规格
    assert any(("螺栓" in t["s"]) or ("M5" in t["s"]) for t in step1), step1
    assert any("密封圈2" in t["s"] for t in step2), step2
    # 绝不出现 process == 钳（工种）
    assert all(t["process"] != "钳" for t in triples), f"工种 leaked into process: {triples}"


def test_substeps_out_of_range_step_no_process_none():
    """step_no=5 超 skeleton 长度 2 → step5 triples 的 process=None。"""
    learner = _learner()
    asm = {
        5: {"name": "钳", "substeps": [{"content": "用 M5×8 螺栓,力矩3.6N·m"}]},
    }
    skeleton = ["装配前准备", "密封圈安装"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    assert triples, f"expected triples for step5: {triples}"
    for t in triples:
        assert t["process"] is None, f"expected None, got {t['process']}"


def test_substeps_spec_fallback_to_material():
    """content 无规格但 material 含规格 → subject 含规格。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "拧紧,力矩3.6N·m", "material": "M5×8 螺栓"},
        ]},
    }
    skeleton = ["装配前准备"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    # 至少一个力矩 triple，subject 含规格（M5/螺栓）
    torque = [t for t in triples if t["r"] == "力矩"]
    assert torque, f"no 力矩 triple: {triples}"
    assert any(("M5" in t["s"]) or ("螺栓" in t["s"]) for t in torque), torque


def test_substeps_empty_asm_returns_empty():
    """asm 空 → 返回 []，不报错。"""
    learner = _learner()
    assert learner._extract_triples_from_substeps({}, []) == []


# ---------------------------------------------------------------------------
# N2+N3 — material triple (proc→material REQUIRES edge for G18a source graph)
# ---------------------------------------------------------------------------

def test_substeps_material_triple_uses_relation():
    """substep 有 material → 产物料 triple {s:process, r:"使用", o:material}。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "安装密封圈", "material": "密封圈"},
        ]},
    }
    skeleton = ["密封圈安装"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    mat = [t for t in triples if t["r"] == "使用"]
    assert mat, f"expected material triple, got {triples}"
    assert any(t["s"] == "密封圈安装" and t["o"] == "密封圈" for t in mat), mat


def test_substeps_material_triple_cleaned_spec_suffix():
    """material 含规格混 (e.g. 螺纹HG/T3596) → 取前段干净名。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "缠绕", "material": "螺纹HG/T3596"},
        ]},
    }
    skeleton = ["缠绕工序"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    mat = [t for t in triples if t["r"] == "使用"]
    assert mat, f"expected material triple: {triples}"
    # 清洗掉规格后缀，object 不含 HG/T
    assert any("HG/T" not in t["o"] for t in mat), mat


def test_substeps_material_triple_multi_materials_all_extracted():
    """一格多物料 (酒精、白绸布、标记笔) → 三条"使用" triple 全提。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "清洁标记", "material": "酒精、白绸布、标记笔"},
        ]},
    }
    skeleton = ["清洁标记"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    mat = [t for t in triples if t["r"] == "使用"]
    assert len(mat) == 3, f"expected 3 material triples, got: {mat}"
    objs = {t["o"] for t in mat}
    assert objs == {"酒精", "白绸布", "标记笔"}, objs


def test_substeps_material_triple_single_material_no_regression():
    """单物料含规格 (密封圈20) → 仍产一条清洗后名"密封圈"（spec_cut 生效）。

    Note: φ 等非 ASCII 规格字符不在原有 spec_cut 字符类内，原管线本不切。
    """
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "安装", "material": "密封圈20"},
        ]},
    }
    skeleton = ["密封圈安装"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    mat = [t for t in triples if t["r"] == "使用"]
    assert len(mat) == 1, f"expected 1 material triple, got: {mat}"
    assert mat[0]["o"] == "密封圈", mat


def test_substeps_material_triple_mixed_separators_empty_segments():
    """混合分隔符 + 空段 → 空段跳过，仍三条。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "清洁标记", "material": "酒精,，白绸布、、标记笔"},
        ]},
    }
    skeleton = ["清洁标记"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    mat = [t for t in triples if t["r"] == "使用"]
    assert len(mat) == 3, f"expected 3 material triples (empty segs skipped), got: {mat}"
    objs = {t["o"] for t in mat}
    assert objs == {"酒精", "白绸布", "标记笔"}, objs


def test_substeps_material_triple_duplicate_segments_deduped():
    """重复段 (酒精、酒精) → 只一条（_add seen-set 去重幂等）。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [
            {"content": "清洁", "material": "酒精、酒精"},
        ]},
    }
    skeleton = ["清洁工序"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    mat = [t for t in triples if t["r"] == "使用"]
    assert len(mat) == 1, f"expected dedup to 1, got: {mat}"
    assert mat[0]["o"] == "酒精", mat


def test_substeps_material_triple_skipped_when_no_process():
    """step_no 越界 process=None → 不产物料 triple (不绑错工序)。"""
    learner = _learner()
    asm = {
        5: {"name": "钳", "substeps": [{"content": "x", "material": "密封圈"}]},
    }
    skeleton = ["装配前准备"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    assert not any(t["r"] == "使用" for t in triples), triples


def test_substeps_material_triple_skipped_when_empty():
    """material 空 → 不产物料 triple。"""
    learner = _learner()
    asm = {
        1: {"name": "钳", "substeps": [{"content": "操作", "material": ""}]},
    }
    skeleton = ["装配前准备"]
    triples = learner._extract_triples_from_substeps(asm, skeleton)
    assert not any(t["r"] == "使用" for t in triples), triples

