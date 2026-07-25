"""Tests for KnowledgeGraph merge + build_from_triples (craft-kg-from-learn N4).

Covers the core of the learn→craft KG feed: triples→KG build + additive
idempotent merge. _feed_craft_kg (thin wrapper over these + save_craft_kg) is
verified end-to-end via the learn endpoint smoke.
"""
from app.services.knowledge_graph import KnowledgeGraph


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
