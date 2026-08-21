"""
KnowledgeGraph - NetworkX-based knowledge relationship graph.

Stores process steps, materials, tools, and parameters as a directed graph.
Supports context expansion for LLM injection and structural validation.

Storage: serialized as JSON dict in Profile.graph field.
Runtime: loaded into NetworkX DiGraph for traversal.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
import re

import networkx as nx

from app.shared.logging import get_logger

logger = get_logger(__name__)

# Node types
NODE_PROCESS_STEP = "process_step"
NODE_MATERIAL = "material"
NODE_TOOL = "tool"
NODE_PARAMETER = "parameter"
NODE_SPEC = "spec"  # 规格(螺柱/螺栓/标准号等,作参数 triple 的 subject)

# Edge types
EDGE_SEQUENTIAL = "sequential"
EDGE_REQUIRES = "requires"
EDGE_DEPENDS_ON = "depends_on"
EDGE_REFERENCES = "references"
EDGE_USED_IN = "used_in"  # 工序 uses 规格 (proc→spec)


class KnowledgeGraph:
    """Directed graph of process knowledge relationships."""

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    # ========================================
    # Node operations
    # ========================================

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        **props: Any,
    ) -> None:
        """Add or update a node."""
        self._graph.add_node(node_id, type=node_type, label=label, **props)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node data, or None if not found."""
        if node_id not in self._graph:
            return None
        data = dict(self._graph.nodes[node_id])
        data["id"] = node_id
        return data

    def has_node(self, node_id: str) -> bool:
        return node_id in self._graph

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    # ========================================
    # Edge operations
    # ========================================

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        **props: Any,
    ) -> None:
        """Add a directed edge. Auto-creates nodes if missing."""
        if source not in self._graph:
            self._graph.add_node(source, type="unknown", label=source)
        if target not in self._graph:
            self._graph.add_node(target, type="unknown", label=target)
        self._graph.add_edge(source, target, type=edge_type, **props)

    # ========================================
    # Query operations
    # ========================================

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        direction: str = "both",
    ) -> List[Dict[str, Any]]:
        """Get neighbor nodes, optionally filtered by edge type and direction.

        Args:
            node_id: The node to query from.
            edge_type: Filter by edge type (e.g. 'requires', 'sequential').
            direction: 'out' (successors), 'in' (predecessors), or 'both'.

        Returns:
            List of neighbor node data dicts.
        """
        if node_id not in self._graph:
            return []

        neighbors: Set[str] = set()
        if direction in ("out", "both"):
            neighbors.update(self._graph.successors(node_id))
        if direction in ("in", "both"):
            neighbors.update(self._graph.predecessors(node_id))

        results: List[Dict[str, Any]] = []
        for nid in neighbors:
            # Filter by edge type
            if edge_type:
                matched = False
                # Check outgoing edge
                if direction in ("out", "both"):
                    edge_data = self._graph.get_edge_data(node_id, nid)
                    if edge_data and edge_data.get("type") == edge_type:
                        matched = True
                # Check incoming edge
                if not matched and direction in ("in", "both"):
                    edge_data = self._graph.get_edge_data(nid, node_id)
                    if edge_data and edge_data.get("type") == edge_type:
                        matched = True
                if not matched:
                    continue
            node_data = dict(self._graph.nodes[nid])
            node_data["id"] = nid
            results.append(node_data)

        return results

    def get_path(self, source_id: str, target_id: str) -> List[str]:
        """Find shortest path between two nodes. Returns node ID list, empty if no path."""
        try:
            return nx.shortest_path(self._graph, source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def expand_context(
        self,
        node_ids: List[str],
        max_hops: int = 2,
        max_nodes: int = 20,
    ) -> List[Dict[str, Any]]:
        """Expand context from seed nodes via BFS.

        Returns up to max_nodes neighbor nodes within max_hops distance.
        """
        visited: Set[str] = set(node_ids)
        frontier: Set[str] = set(node_ids)
        results: List[Dict[str, Any]] = []

        for _ in range(max_hops):
            next_frontier: Set[str] = set()
            for nid in frontier:
                if nid not in self._graph:
                    continue
                for succ in self._graph.successors(nid):
                    if succ not in visited:
                        next_frontier.add(succ)
                for pred in self._graph.predecessors(nid):
                    if pred not in visited:
                        next_frontier.add(pred)
            frontier = next_frontier
            visited.update(frontier)

        # Collect results
        for nid in visited:
            if nid in node_ids:
                continue  # Skip seed nodes
            node_data = dict(self._graph.nodes[nid])
            node_data["id"] = nid
            results.append(node_data)
            if len(results) >= max_nodes:
                break

        return results

    def find_sequential_gaps(self) -> List[Tuple[str, str]]:
        """Find process_step nodes with no outgoing sequential edge (potential gaps).

        Returns list of (node_id, label) for nodes that are process_steps
        but have no 'sequential' successor.
        """
        gaps: List[Tuple[str, str]] = []
        for nid in self._graph.nodes:
            node = self._graph.nodes[nid]
            if node.get("type") != NODE_PROCESS_STEP:
                continue
            # Check if any outgoing edge is sequential
            has_seq = False
            for _, _, data in self._graph.edges(nid, data=True):
                if data.get("type") == EDGE_SEQUENTIAL:
                    has_seq = True
                    break
            if not has_seq:
                gaps.append((nid, node.get("label", nid)))
        return gaps

    def find_parameter_conflicts(self) -> List[Dict[str, Any]]:
        """Find parameter nodes with conflicting values connected to the same process step.

        Returns list of conflict descriptions.
        """
        conflicts: List[Dict[str, Any]] = []
        for nid in self._graph.nodes:
            node = self._graph.nodes[nid]
            if node.get("type") != NODE_PROCESS_STEP:
                continue
            # Collect all parameter neighbors
            params: Dict[str, List[str]] = {}
            for _, target, data in self._graph.out_edges(nid, data=True):
                if data.get("type") == EDGE_DEPENDS_ON:
                    target_node = self._graph.nodes[target]
                    if target_node.get("type") == NODE_PARAMETER:
                        label = target_node.get("label", target)
                        params.setdefault(label, []).append(target)
            # Check for duplicates (same label, multiple nodes)
            for label, node_ids in params.items():
                if len(node_ids) > 1:
                    conflicts.append({
                        "process_step": nid,
                        "parameter_label": label,
                        "conflicting_nodes": node_ids,
                    })
        return conflicts

    # ========================================
    # Build from profile data
    # ========================================

    @classmethod
    def build_from_triples(
        cls, triples: List[Dict[str, str]], source: Optional[str] = None
    ) -> "KnowledgeGraph":
        """Build graph from legacy triple format {s, r, o}.

        source: when non-empty, all node/edge ids get a "{source}::" prefix so
        the same spec learned from different documents never overwrites the
        earlier one (different ids → cross-source merge keeps both; same
        source re-learn → same ids → merge_from skips, idempotent). Labels
        stay unprefixed so display/seed matching is unaffected. source=None
        keeps legacy behavior exactly.
        """
        kg = cls()

        def _sid(text: str) -> str:
            return f"{source}::{_safe_id(text)}" if source else _safe_id(text)

        for t in triples:
            s, r, o = t.get("s", ""), t.get("r", ""), t.get("o", "")
            if not s or not o:
                continue

            if r == "下一步":
                kg.add_node(_sid(s), NODE_PROCESS_STEP, s)
                kg.add_node(_sid(o), NODE_PROCESS_STEP, o)
                kg.add_edge(_sid(s), _sid(o), EDGE_SEQUENTIAL)
            elif r == "使用":
                kg.add_node(_sid(s), NODE_PROCESS_STEP, s)
                # Classify: tool or material
                tool_keywords = ("扳手", "量具", "工具", "设备", "仪器", "焊机", "卡尺")
                ntype = NODE_TOOL if any(kw in o for kw in tool_keywords) else NODE_MATERIAL
                kg.add_node(_sid(o), ntype, o)
                kg.add_edge(_sid(s), _sid(o), EDGE_REQUIRES)
            elif r in ("温度", "力矩", "压力", "时间", "速度", "公差", "硬度"):
                spec_id = _sid(s)
                param_id = _sid(f"{s}_{r}")
                is_spec = _is_spec(s)
                # 规格 subject 建 NODE_SPEC（若非规格退化为 PROCESS_STEP，向后兼容）
                spec_type = NODE_SPEC if is_spec else NODE_PROCESS_STEP
                kg.add_node(spec_id, spec_type, s)
                kg.add_node(param_id, NODE_PARAMETER, o)
                kg.add_edge(spec_id, param_id, EDGE_DEPENDS_ON, relation=r)
                # used_in (proc→spec) 只在真规格 subject 时建；非规格 subject(工序动作) 不假装规格-工序关联
                if is_spec:
                    proc = t.get("process")
                    if proc:
                        proc_id = _sid(proc)
                        kg.add_node(proc_id, NODE_PROCESS_STEP, proc)
                        kg.add_edge(proc_id, spec_id, EDGE_USED_IN, relation=s)
            elif r == "标准":
                kg.add_node(_sid(s), NODE_PROCESS_STEP, s)
                kg.add_node(_sid(o), NODE_MATERIAL, o)  # Standards treated as material nodes
                kg.add_edge(_sid(s), _sid(o), EDGE_REFERENCES)
            elif r == "禁止":
                # Safety constraint — store as node property on the process step
                sid = _sid(s)
                kg.add_node(sid, NODE_PROCESS_STEP, s)
                existing = kg._graph.nodes[sid].get("prohibitions", "")
                if existing:
                    kg._graph.nodes[sid]["prohibitions"] = f"{existing}; {o}"
                else:
                    kg._graph.nodes[sid]["prohibitions"] = o
            else:
                # Generic: source → target
                kg.add_node(_sid(s), NODE_PROCESS_STEP, s)
                kg.add_node(_sid(o), NODE_MATERIAL, o)
                kg.add_edge(_sid(s), _sid(o), EDGE_REQUIRES, relation=r)

        return kg

    # ========================================
    # Merge (additive, idempotent)
    # ========================================

    def merge_from(self, other: "KnowledgeGraph") -> None:
        """Fold another KG's nodes/edges into this one (additive, idempotent).

        Used to merge a per-learn triples-built KG into the global craft_kg.
        Nodes/edges already present are skipped — node ids come from _safe_id,
        so the same process step learned from different files merges into one
        node (cross-file dedup of same-named steps).
        """
        for nid, props in other._graph.nodes(data=True):
            if nid not in self._graph:
                self._graph.add_node(nid, **dict(props))
        for src, tgt, data in other._graph.edges(data=True):
            if not self._graph.has_edge(src, tgt):
                self._graph.add_edge(src, tgt, **dict(data))

    # ========================================
    # Serialization
    # ========================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        nodes: Dict[str, Any] = {}
        for nid in self._graph.nodes:
            data = dict(self._graph.nodes[nid])
            data.pop("id", None)  # id is the key
            nodes[nid] = data

        edges: List[Dict[str, Any]] = []
        for src, tgt, data in self._graph.edges(data=True):
            edges.append({"source": src, "target": tgt, **data})

        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        """Deserialize from dict."""
        kg = cls()
        for nid, props in data.get("nodes", {}).items():
            kg._graph.add_node(nid, **props)
        for edge in data.get("edges", []):
            src = edge.get("source")
            tgt = edge.get("target")
            if not src or not tgt:
                continue
            # Copy remaining props (exclude source/target)
            attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
            kg._graph.add_edge(src, tgt, **attrs)
        return kg

    def to_context_text(
        self,
        seed_node_ids: Optional[List[str]] = None,
        max_tokens: int = 500,
    ) -> str:
        """Generate text for LLM context injection.

        If seed_node_ids provided, expand from those nodes.
        Otherwise, render full graph summary.
        """
        if self._graph.number_of_nodes() == 0:
            return ""

        parts: List[str] = []

        if seed_node_ids:
            # Expand from seeds and render
            expanded = self.expand_context(seed_node_ids, max_hops=2, max_nodes=15)
            all_ids = set(seed_node_ids) | {n["id"] for n in expanded}
        else:
            all_ids = set(self._graph.nodes)

        # Render process steps with their connections
        for nid in sorted(all_ids):
            if nid not in self._graph:
                continue
            node = self._graph.nodes[nid]
            label = node.get("label", nid)
            ntype = node.get("type", "")

            if ntype == NODE_PROCESS_STEP:
                line = f"[工序] {label}"
                # Outgoing edges
                for _, target, data in self._graph.out_edges(nid, data=True):
                    target_node = self._graph.nodes[target]
                    target_label = target_node.get("label", target)
                    etype = data.get("type", "")
                    if etype == EDGE_SEQUENTIAL:
                        line += f" → 下一步: {target_label}"
                    elif etype == EDGE_REQUIRES:
                        rel = data.get("relation", "需要")
                        line += f" | {rel}: {target_label}"
                    elif etype == EDGE_DEPENDS_ON:
                        rel = data.get("relation", "")
                        line += f" | {rel}: {target_label}"
                    elif etype == EDGE_REFERENCES:
                        line += f" | 参考: {target_label}"
                    elif etype == EDGE_USED_IN:
                        line += f" | 规格: {target_label}"
                # Prohibitions
                if node.get("prohibitions"):
                    line += f" | 禁止: {node['prohibitions']}"
                parts.append(line)
            elif ntype == NODE_SPEC:
                line = f"[规格] {label}"
                # 展开 spec→param 显示参数值
                for _, tgt, edata in self._graph.out_edges(nid, data=True):
                    if edata.get("type") == EDGE_DEPENDS_ON:
                        tgt_label = self._graph.nodes[tgt].get("label", tgt)
                        line += f" | {edata.get('relation', '参数')}: {tgt_label}"
                parts.append(line)
            elif ntype == NODE_PARAMETER:
                line = f"[参数] {label}"
                parts.append(line)
            elif ntype == NODE_TOOL:
                line = f"[工具] {label}"
                parts.append(line)
            elif ntype == NODE_MATERIAL:
                line = f"[材料/标准] {label}"
                parts.append(line)

        text = "\n".join(parts)

        # Rough token estimate (4 chars ≈ 1 token for Chinese)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return text


SPEC_KEYWORDS = (
    "M", "GB/T", "GB-T", "GB/", "\u87ba\u67f1", "\u87ba\u6813", "\u87ba\u9489",
    "\u5bc6\u5c01\u5708", "O\u578b", "O\u5708", "\u710a\u6761", "\u710a\u4e1d", "\u6d82\u6599", "\u6d82\u6f06",
    "\u6954\u73af", "T2D", "\u7535\u7f06",
)


def _is_spec(text: str) -> bool:
    """\u5224\u5b9a subject \u662f\u5426\u89c4\u683c(\u800c\u975e\u5de5\u5e8f\u540d)\u2014\u2014\u542b\u89c4\u683c\u5173\u952e\u8bcd\u6216 M\\d+ \u87ba\u7eb9\u4ee3\u53f7\u3002"""
    if not text:
        return False
    if re.search(r"M\d+", text):
        return True
    return any(k in text for k in SPEC_KEYWORDS)


def _safe_id(text: str) -> str:
    """Convert text to a safe node ID."""
    return re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]", "_", text.strip())[:64]


# ========================================
# Global craft knowledge graph
# Decoupled from Profile.graph (per-domain profile); this is the cross-domain
# process KG persisted to data/knowledge_graph.json, loaded at startup.
# ========================================
import json
import os


def get_craft_kg_path() -> str:
    """Path to the global craft knowledge graph JSON file."""
    from app.config import settings
    return os.path.join(str(settings.DATA_DIR), "knowledge_graph.json")


def load_craft_kg() -> KnowledgeGraph:
    """Load global craft KG from data/knowledge_graph.json (empty graph if missing/corrupt)."""
    path = get_craft_kg_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return KnowledgeGraph.from_dict(data)
    except Exception as e:
        logger.warning(f"load_craft_kg failed: {e}")
    return KnowledgeGraph()


def save_craft_kg(kg: KnowledgeGraph) -> None:
    """Persist global craft KG to data/knowledge_graph.json."""
    path = get_craft_kg_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(kg.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"save_craft_kg failed: {e}")


# Module-level global instance (populated at startup; import-safe: instance
# identity is stable, only its internal _graph is swapped on reload).
craft_kg: KnowledgeGraph = KnowledgeGraph()


def init_craft_kg() -> None:
    """Load the global craft KG file into the module-level craft_kg instance."""
    loaded = load_craft_kg()
    craft_kg._graph = loaded._graph
    logger.info(
        f"craft_kg loaded: {craft_kg.node_count} nodes / {craft_kg.edge_count} edges"
    )
