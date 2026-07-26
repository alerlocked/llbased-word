# PLAN: craft KG 规格-工序关联改造（B 方案）

> slug: `craft-kg-quality` | ALIGN: `ALIGN-craft-kg-quality.md`（模糊点清零）| seal 后不可变

## Context（为什么改）
2026-07-26 端到端验证（云端 qwen3）发现 craft_kg 灌了数据但检索时 KG 节点查不到——`_search_knowledge_graph` query 是 G25a 工序名，KG 节点 label 是规格/参数，两维度不通，seed_ids 命中 0。根因：`build_from_triples` 把规格当 `NODE_PROCESS_STEP`（knowledge_graph.py:260）+ triple 无工序上下文（规格节点与工序节点孤立）。目标：建"规格-工序"关联，让工序名查到关联规格，KG 真贡献 aux_standards。

## 改动清单

| 文件 | 改什么 |
|---|---|
| `backend/app/services/document_profile_learner.py` | **N1** `spec_patterns`（:151-161）扩展：`螺[栓钉]`→`螺[栓钉柱]`（加柱）+ 反序 `螺[栓钉柱]\s*M\d+`（"螺柱 M5"）+ `M\d+[-×xX]\d+`（M5×8）。**N2** `_add`（:130）加 `process: str=None` + triple 加 `"process"`（:136）；抽 `_collect_headers(content)`（复用 :254-256 正则）+ `_guess_current_section` 改调它；新增 `_section_at(pos)` 按位置取最近前置工序标题（放宽：任何数字标题都算候选，去 :262-270 工艺关键词过滤）；Pattern 1（:177-178）改传 `process=self._section_at(match.start())`。 |
| `backend/app/services/knowledge_graph.py` | **N3** 常量（:17-27）加 `NODE_SPEC="spec"` + `EDGE_USED_IN="used_in"`；规格参数 branch（:259-262）改：`_is_spec(s)`（照搬 :255-256 tool_keywords 范式：M\d+/GB-T/螺[栓钉柱]/密封圈/T2D/楔环）→ 建 `NODE_SPEC`（非 PROCESS_STEP）+ spec→param(EDGE_DEPENDS_ON)；读 `t.get("process")` 非空 → 建工序节点 NODE_PROCESS_STEP + **边 proc→spec(EDGE_USED_IN, relation=规格名)**；process 空退化现状（向后兼容）。**N4** `to_context_text`（:367-396）：NODE_PROCESS_STEP 分支 out_edges 加 `elif etype==EDGE_USED_IN: line+=" \| 规格: {target_label}"`；新增 NODE_SPEC 渲染分支 `[规格] {label}` + 展开 spec→param。 |
| `backend/tests/test_knowledge_graph.py` | **N5** 追加：`_is_spec` 判定 + build NODE_SPEC + proc→spec(USED_IN) 边 + to_context_text 规格渲染 + **按工序查到规格**（build 带 process KG → query 工序名 → seed 工序 → expand 规格）。 |
| `backend/tests/test_document_profile_learner.py` | **N5** 规格 pattern（柱/反序/M×，含负例 M58 个零件不抽）+ `_section_at(pos)` 按位置取 + triple 带 process。 |

## 禁区
- 不改 `_search_knowledge_graph`（hierarchical_context.py:968，建 proc→spec 边后工序 seed `kw in label` 自动命中）
- 不碰 DB knowledge_search（MaterialCatalog/StandardClause，aux 现有来源）/ 不改前端 / 不动其他章节 / 不上向量
- 不重写 `_extract_triples`/`build_from_triples`（加规则加字段，最小改）/ 不改 `_safe_id`

## 节点顺序（每节点 1 commit，顺序依赖）
N1（spec_patterns）→ N2（process 字段 + _section_at）→ N3（build + 节点类型 + proc→spec 边）→ N4（渲染）→ N5（测试 + 端到端）。

## 验证
- 单测：`cd backend && pytest tests/test_knowledge_graph.py tests/test_document_profile_learner.py -v`
- 全量回归：`pytest tests/` 0 新 fail（基线 681 passed）
- 端到端（云端 qwen3）：删 `data/knowledge_graph.json`（旧脏 schema）→ learn documents/1 → `python -c "..._search_knowledge_graph('螺钉安装 插头安装',600)"` 输出含 `## 知识图谱`+`[规格]` → generation_mode=generate 触发 G25a → 日志 `g25a_aux_injected has_aux=True` 且 aux 含规格（不只 DB）。

## 风险注
- HTML 规格粘连（M58/M410）：去 tag 后多已分开（task2 实证），N1 单测用真实 content 兜底；粘连严重则 spec_patterns 用 `螺[栓钉柱]?\s*M\d+(?:\s*\d+)?` 容错。
- `_section_at` 标题识别：learn content 多已纯文本，N2 单测验证；漏抽则正则放宽。
- 旧 `knowledge_graph.json` schema 脏：N5 显式删文件重 learn（一次性，非代码）。

## 复用现有实现
`_guess_current_section` headers 正则 → `_collect_headers`；"使用"分支 tool_keywords 判类型 → `_is_spec` 范式；`merge_from`（:288）幂等 + `_safe_id` 跨文件去重 → proc→spec 边汇聚；`expand_context`（:146）BFS 2 跳 → 工序 seed 第一跳到规格；KG 已有真工序节点（螺钉安装/插头安装）→ query 天然命中。
