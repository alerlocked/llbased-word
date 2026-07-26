"""Tests for G18a source/remarks fill from craft_kg material→process edges (N2+N3).

Covers:
- _g18a_material_process: reverse-lookup REQUIRES edge source = process label
- _g18a_is_std_or_consumable: fastener/coded/consumable classification
- _fill_g18a_from_kg: end-to-end row fill (source + remarks, 待补 overwrite,
  std/consumable blanking, no-fabrication on graph miss)
"""
import pytest

from app.services.knowledge_graph import KnowledgeGraph
from app.agents.orchestrator.orchestrator import ProcessOrchestrator


@pytest.fixture
def kg_with_edges():
    """A fresh KG with proc→material REQUIRES edges, swapped into the craft_kg
    singleton's _graph for the duration of the test."""
    kg = KnowledgeGraph.build_from_triples([
        {"s": "密封圈安装", "r": "使用", "o": "密封圈", "process": "密封圈安装"},
        {"s": "电缆装配", "r": "使用", "o": "电缆", "process": "电缆装配"},
    ])
    import app.services.knowledge_graph as kgmod
    saved = kgmod.craft_kg._graph
    kgmod.craft_kg._graph = kg._graph
    try:
        yield kgmod.craft_kg
    finally:
        kgmod.craft_kg._graph = saved


# ---------------------------------------------------------------------------
# _g18a_material_process — graph reverse lookup
# ---------------------------------------------------------------------------

def test_material_process_finds_proc(kg_with_edges):
    """密封圈 → 密封圈安装 (REQUIRES source)."""
    assert ProcessOrchestrator._g18a_material_process("密封圈") == "密封圈安装"


def test_material_process_substring_match(kg_with_edges):
    """label 包含/被包含都算命中: 'O型密封圈' 命中 '密封圈' 节点。"""
    assert ProcessOrchestrator._g18a_material_process("O型密封圈") == "密封圈安装"


def test_material_process_miss_returns_empty(kg_with_edges):
    """graph 无边 → 空字符串, 不臆造。"""
    assert ProcessOrchestrator._g18a_material_process("不存在的物料XYZ") == ""


def test_material_process_empty_input():
    """空输入 → 空。"""
    assert ProcessOrchestrator._g18a_material_process("") == ""
    assert ProcessOrchestrator._g18a_material_process("   ") == ""


def test_material_process_empty_graph(monkeypatch):
    """craft_kg 空图 → 空, 不报错。"""
    import app.services.knowledge_graph as kgmod
    empty = KnowledgeGraph()
    monkeypatch.setattr(kgmod.craft_kg, "_graph", empty._graph)
    assert ProcessOrchestrator._g18a_material_process("密封圈") == ""


# ---------------------------------------------------------------------------
# _g18a_is_std_or_consumable — classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["螺钉", "六角螺栓", "螺母M5", "弹簧垫圈", "圆柱销"])
def test_std_part_recognized(name):
    assert ProcessOrchestrator._g18a_is_std_or_consumable(name) is True


@pytest.mark.parametrize("name", ["GB/T70螺钉", "GB-T5783", "QJB1010", "QJ配件"])
def test_std_code_recognized(name):
    assert ProcessOrchestrator._g18a_is_std_or_consumable(name) is True


@pytest.mark.parametrize("name", ["白棉布", "无水乙醇", "润滑脂", "密封胶"])
def test_consumable_recognized(name):
    assert ProcessOrchestrator._g18a_is_std_or_consumable(name) is True


@pytest.mark.parametrize("name", ["密封圈", "电缆", "壳体", "支架"])
def test_main_material_not_std(name):
    """主物料/关键配件 → False (要写 remarks)。"""
    assert ProcessOrchestrator._g18a_is_std_or_consumable(name) is False


# ---------------------------------------------------------------------------
# _fill_g18a_from_kg — end-to-end row fill
# ---------------------------------------------------------------------------

def test_fill_source_from_graph_overwrites_placeholder(kg_with_edges):
    """source=待补 + 主物料 → source=工序 (graph 命中)。"""
    rows = [{"part_code": "A1", "part_name": "密封圈", "source": "待补", "remarks": "待补"}]
    ProcessOrchestrator._fill_g18a_from_kg(rows)
    assert rows[0]["source"] == "密封圈安装"


def test_fill_remarks_main_material_writes_proc(kg_with_edges):
    """主物料密封圈 + graph 命中 → remarks=密封圈安装。"""
    rows = [{"part_code": "A1", "part_name": "密封圈", "source": "待补", "remarks": "待补"}]
    ProcessOrchestrator._fill_g18a_from_kg(rows)
    assert rows[0]["remarks"] == "密封圈安装"


def test_fill_remarks_std_part_blank(kg_with_edges):
    """标准件螺钉 → remarks 空 (即使 graph 命中也不写)。"""
    rows = [{"part_code": "B1", "part_name": "螺钉", "source": "待补", "remarks": "待补"}]
    ProcessOrchestrator._fill_g18a_from_kg(rows)
    assert rows[0]["remarks"] == ""


def test_fill_remarks_consumable_blank(kg_with_edges):
    """耗材白棉布 → remarks 空。"""
    rows = [{"part_code": "C1", "part_name": "白棉布", "source": "待补", "remarks": "待补"}]
    ProcessOrchestrator._fill_g18a_from_kg(rows)
    assert rows[0]["remarks"] == ""


def test_fill_graph_miss_leaves_blank_no_fabrication(kg_with_edges):
    """graph 没命中的主物料 → source/remarks 都空, 不臆造。"""
    rows = [{"part_code": "D1", "part_name": "未知零件", "source": "待补", "remarks": "待补"}]
    ProcessOrchestrator._fill_g18a_from_kg(rows)
    assert rows[0]["source"] == ""
    assert rows[0]["remarks"] == ""


def test_fill_does_not_overwrite_real_value(kg_with_edges):
    """已有真值 (非待补) 不被覆盖。"""
    rows = [{"part_code": "A1", "part_name": "密封圈",
             "source": "采购清单", "remarks": "关键件"}]
    ProcessOrchestrator._fill_g18a_from_kg(rows)
    assert rows[0]["source"] == "采购清单"
    assert rows[0]["remarks"] == "关键件"


def test_fill_empty_rows_noop():
    """空 rows → 不报错。"""
    ProcessOrchestrator._fill_g18a_from_kg([])
