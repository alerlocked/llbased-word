"""Tests for KnowledgeGraph merge + build_from_triples (craft-kg-from-learn N4).

Covers the core of the learn→craft KG feed: triples→KG build + additive
idempotent merge. _feed_craft_kg (thin wrapper over these + save_craft_kg) is
verified end-to-end via the learn endpoint smoke.
"""
from app.services.knowledge_graph import (
    KnowledgeGraph,
    NODE_SPEC,
    NODE_PROCESS_STEP,
    NODE_PARAMETER,
    EDGE_USED_IN,
    EDGE_DEPENDS_ON,
    _is_spec,
    _safe_id,
)


def test_build_from_triples_nodes_and_edges():
    """使用/下一步/参数/标准 relations map to typed nodes + edges."""
    kg = KnowledgeGraph.build_from_triples([
        {"s": "装配A", "r": "使用", "o": "扭矩扳手"},
        {"s": "装配A", "r": "下一步", "o": "装配B"},
    ])
    # 装配A, 扭矩扳手, 装配B = 3 nodes; 使用 + 下一步 = 2 edges
    assert kg.node_count == 3
    assert kg.edge_count == 2


def test_build_from_triples_parameter_node():
    """Numeric relations (温度/压力/力矩...) become parameter nodes."""
    kg = KnowledgeGraph.build_from_triples([{"s": "气密检查", "r": "压力", "o": "0.5MPa"}])
    # 气密检查 (process_step) + 0.5MPa (parameter) = 2 nodes, 1 depends_on edge
    assert kg.node_count == 2
    assert kg.edge_count == 1


def test_merge_from_additive_then_idempotent():
    """merge_from adds nodes/edges; re-merging the same KG does not duplicate."""
    kg = KnowledgeGraph()
    other = KnowledgeGraph.build_from_triples([
        {"s": "装配A", "r": "使用", "o": "扭矩扳手"},
        {"s": "装配A", "r": "下一步", "o": "装配B"},
    ])
    kg.merge_from(other)
    assert kg.node_count == 3
    assert kg.edge_count == 2

    # Re-merge must be idempotent (same node ids → no duplication)
    kg.merge_from(other)
    assert kg.node_count == 3
    assert kg.edge_count == 2


def test_merge_from_overlapping_step_dedups():
    """Same-named process step learned from two files merges into one node."""
    kg = KnowledgeGraph()
    a = KnowledgeGraph.build_from_triples([{"s": "装配A", "r": "使用", "o": "扳手"}])
    b = KnowledgeGraph.build_from_triples([
        {"s": "装配A", "r": "使用", "o": "扳手"},  # overlap with a
        {"s": "焊接C", "r": "温度", "o": "200℃"},  # new
    ])
    kg.merge_from(a)
    kg.merge_from(b)
    # 装配A + 扳手 dedup across a/b; 焊接C + 200℃ new → 4 nodes total
    assert kg.node_count == 4


def test_merge_from_empty_noop():
    """Merging an empty KG is a no-op."""
    kg = KnowledgeGraph.build_from_triples([{"s": "装配A", "r": "使用", "o": "扳手"}])
    before = kg.node_count
    kg.merge_from(KnowledgeGraph())  # empty
    assert kg.node_count == before


# ========================================
# craft-kg-quality N3+N4: spec nodes + proc→spec edges
# ========================================

def test_is_spec_keywords_and_thread_code():
    """_is_spec flags spec subjects (螺纹代号 / 规格关键词), not process names."""
    assert _is_spec("M5螺柱") is True            # M\d+ 螺纹代号
    assert _is_spec("GB/T68-2000") is True       # 标准号关键词
    assert _is_spec("密封圈2") is True            # 规格关键词
    assert _is_spec("装配") is False              # 纯工序名
    assert _is_spec("焊接") is False              # 纯工序名
    assert _is_spec("") is False


def test_build_spec_branch_with_process():
    """规格 triple 携带 process → spec 节点 + proc 节点 + proc→spec 边 + spec→param 边。"""
    kg = KnowledgeGraph.build_from_triples([
        {"s": "M5螺柱", "r": "力矩", "o": "3.6N·m", "process": "装配"},
    ])
    spec_id = _safe_id("M5螺柱")
    proc_id = _safe_id("装配")
    param_id = _safe_id("M5螺柱_力矩")

    # 规格节点建为 NODE_SPEC
    assert kg.get_node(spec_id)["type"] == NODE_SPEC
    # 工序节点建为 NODE_PROCESS_STEP
    assert kg.get_node(proc_id)["type"] == NODE_PROCESS_STEP
    # 参数节点
    assert kg.get_node(param_id)["type"] == NODE_PARAMETER

    # proc→spec (used_in) 边 + spec→param (depends_on) 边
    assert kg._graph.get_edge_data(proc_id, spec_id)["type"] == EDGE_USED_IN
    assert kg._graph.get_edge_data(spec_id, param_id)["type"] == EDGE_DEPENDS_ON


def test_build_spec_branch_process_missing_backcompat():
    """无 process 字段 → 建规格节点但不建工序节点、无 used_in 边（向后兼容）。"""
    kg = KnowledgeGraph.build_from_triples([
        {"s": "M5螺柱", "r": "力矩", "o": "3.6N·m"},
    ])
    spec_id = _safe_id("M5螺柱")
    proc_id = _safe_id("装配")

    # 规格节点仍建（subject 命中 _is_spec）
    assert kg.get_node(spec_id)["type"] == NODE_SPEC
    # 无工序节点
    assert kg.has_node(proc_id) is False
    # 无 used_in 边
    for _, _, data in kg._graph.edges(data=True):
        assert data.get("type") != EDGE_USED_IN


def test_to_context_text_renders_spec_with_param():
    """to_context_text 从工序 seed 展开 → 输出 [规格] 行 + 参数值。"""
    kg = KnowledgeGraph.build_from_triples([
        {"s": "M5螺柱", "r": "力矩", "o": "3.6N·m", "process": "装配"},
    ])
    proc_id = _safe_id("装配")
    text = kg.to_context_text(seed_node_ids=[proc_id])
    assert "[规格] M5螺柱" in text
    assert "力矩: 3.6N·m" in text


def test_search_by_process_reaches_spec_end_to_end():
    """模拟 _search_knowledge_graph 的 seed 逻辑:label 含工序名 → expand 含规格节点。"""
    kg = KnowledgeGraph.build_from_triples([
        {"s": "M5螺柱", "r": "力矩", "o": "3.6N·m", "process": "装配"},
    ])
    query = "装配"
    # Seed:工序节点 label 含 query（模拟 hierarchical_context seed 命中）
    seeds = [
        nid for nid in kg._graph.nodes
        if kg._graph.nodes[nid].get("type") == NODE_PROCESS_STEP
        and query in kg._graph.nodes[nid].get("label", "")
    ]
    assert seeds, "工序 seed 应命中"

    expanded = kg.expand_context(seeds, max_hops=2)
    expanded_types = {n["id"]: n["type"] for n in expanded}
    assert _safe_id("M5螺柱") in expanded_types
    assert expanded_types[_safe_id("M5螺柱")] == NODE_SPEC


# ========================================
# craft-kg-quality N3 guard: used_in only when subject is a real spec
# ========================================

def test_build_non_spec_subject_no_used_in_edge():
    """非规格 subject(工序动作,如开关按钮拧紧) + process → 仍建 process_step + 参数 +
    depends_on, 但不建 used_in 边(不假装规格-工序关联)。"""
    # 先确认 subject 确实非规格
    assert _is_spec("开关按钮拧紧") is False

    kg = KnowledgeGraph.build_from_triples([
        {"s": "开关按钮拧紧", "r": "力矩", "o": "1.9N·m", "process": "四五舱对接"},
    ])
    step_id = _safe_id("开关按钮拧紧")
    param_id = _safe_id("开关按钮拧紧_力矩")
    proc_id = _safe_id("四五舱对接")

    # subject 退化为 PROCESS_STEP（不是 SPEC）
    assert kg.get_node(step_id)["type"] == NODE_PROCESS_STEP
    # 参数节点仍在
    assert kg.get_node(param_id)["type"] == NODE_PARAMETER
    # depends_on 边仍在
    assert kg._graph.get_edge_data(step_id, param_id)["type"] == EDGE_DEPENDS_ON
    # 关键：无 used_in 边（proc→step 不建）
    assert kg._graph.get_edge_data(proc_id, step_id) is None
    for _, _, data in kg._graph.edges(data=True):
        assert data.get("type") != EDGE_USED_IN


def test_build_spec_subject_still_gets_used_in_edge():
    """对照:规格 subject(T2D30070) + process → 仍有 used_in 边(守卫不误伤真规格)。"""
    assert _is_spec("T2D30070") is True

    kg = KnowledgeGraph.build_from_triples([
        {"s": "T2D30070", "r": "力矩", "o": "1.9N·m", "process": "四五舱对接"},
    ])
    spec_id = _safe_id("T2D30070")
    proc_id = _safe_id("四五舱对接")

    # 规格节点
    assert kg.get_node(spec_id)["type"] == NODE_SPEC
    # proc→spec used_in 边仍建
    assert kg._graph.get_edge_data(proc_id, spec_id)["type"] == EDGE_USED_IN
