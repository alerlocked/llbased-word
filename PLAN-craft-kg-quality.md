# PLAN: craft KG 规格-工序关联改造（B 方案 v2 — 纠错：接 G25a 表格 extract）

> slug: `craft-kg-quality` | **v2（2026-07-26 纠错）**：v1 的 N2 靠章节标题取工序名失败（装配文件无清晰工序标题 + G25a「工序名称」列填工种非工序名），改 N2' 接 G25a source-driven extract，process=G19a skeleton 真工序名 | seal 后不可变

## Context（为什么改 + 为什么 v2）
craft_kg 灌了规格数据但检索时查不到（query 工序名 vs KG 规格名两维度不通），aux 全靠 DB。B 方案建规格-工序关联。

**v1 纠错根因**：N2 的 `_section_at` 靠章节标题（`3.1/3.2`）取工序名 —— 实测装配文件这些是规程条款非工序标题（`_collect_headers` 0 headers）；且 G25a 表格「工序名称」列填的是**工种（钳/机）**非真工序名。真工序名在 **G19a 工艺流程图**（`extract_process_steps` 的 skeleton）+ substep.content 编号开头。

**v2**：废弃 N2 的 `_section_at` 路径，改 **N2'：learn 接 `extract_assembly_steps`**（生成时用的一套，已处理 colspan），`process = skeleton[step_no-1]`（G19a 真工序名），规格/参数从 substep.content 提。N1 + N3+N4 保留（已 commit + 设计正确）。

## 改动清单

| 文件 | 改什么 |
|---|---|
| `backend/app/services/document_profile_learner.py` | **N1 ✅ 已 commit（3100c2d）** spec_patterns 12 条保留。**N2 的 `_section_at` 路径废弃**（装配文件无效；`_collect_headers`/`_section_at` 保留给 Pattern 3/5 整篇兜底，不删）。**N2' 新增**：`_extract_triples_from_substeps(asm, skeleton)` —— 对每个 step_no，`process = skeleton[step_no-1]`（越界/数量不一致→None，比绑错好），该 step 下每个 substep 的 `content` 跑现有 `qty_patterns`/`spec_patterns`（复用，不重写）+ 规格 fallback 查 `substep.material`，`_add(s, r, o, process=skeleton真工序名)`。`learn_from_content` 加可选参 `assembly_steps`/`skeleton_steps`：有则 `_extract_triples_from_substeps` merge 进 `features["triples"]`，无则现路径（兼容非 G25a 文档）。 |
| `backend/app/services/knowledge_graph.py` | **N3+N4 ✅ 已 commit（4af7222）** 常量 NODE_SPEC/EDGE_USED_IN + `_is_spec` + build 规格 branch（规格建 NODE_SPEC + 读 process 建 proc→spec 边）+ `to_context_text` 规格/工序渲染。**无需再改**。 |
| `backend/app/api/profile.py` | **N2' learn 端点接 extract**：`learn-batch`(:364)/`learn-file`(:274) 对 doc_dir 调 `hierarchical_context.extract_assembly_steps(str(mid))` + `extract_process_steps(str(mid))`，asm 非空则传 `learn_from_content(..., assembly_steps=asm, skeleton_steps=skel)`；asm 空（非装配文档）则 fallback 现平文本路径。`learn`(:242 纯文本入参) 不改。 |

## 禁区
- 不改 `_search_knowledge_graph`（建 proc→spec 边后自动生效）
- 不碰 DB knowledge_search / 不改前端 / 不上向量
- **不重写 `extract_assembly_steps`**（复用，它已处理 colspan + 按列名读）
- **process 不用 `asm[k]["name"]`**（那是工种"钳"），用 `skeleton`（G19a 真工序名）
- 不改 `_safe_id` / 不重写 `_extract_triples`（加方法 + 可选参，最小改）

## 节点顺序
N1 ✅ → N3+N4 ✅ → **N2'（新，本次重点）** → N5。N2' 一个 commit：document_profile_learner `_extract_triples_from_substeps` + `learn_from_content` 加参 + profile.py learn 端点接 extract。

## 验证
- 单测：`test_document_profile_learner.py` 加 `_extract_triples_from_substeps`（mock asm+skeleton → triple 的 process=skeleton[i]，规格从 content 提）+ 越界保护（step_no 超 skeleton 长度 → process=None）
- 全量回归：`pytest tests/` 0 新 fail（基线 695）
- 端到端（云端 qwen3）：删 `data/knowledge_graph.json` → learn-batch/learn-file documents/1（接 extract）→ 验 KG 有 proc→spec 边（proc=G19a 真工序名 + spec=规格节点）→ `_search_knowledge_graph(真工序名)` 输出含 `[规格]`（KG 部分非空，不只 DB）→ 真生成 G25a `g25a_aux_injected has_aux=True` aux 含规格

## 风险
1. **G19a skeleton 与 G25a step_no 对齐**：生成链路隐含 `skeleton[i]=G25a step i+1`。learn 加越界保护 + 数量校验（不一致→process=None，比绑错好）。
2. **规格在 substep.material 列**：实测 step5 material="螺纹HG/T3596"。content 找不到规格时 fallback 查 material。
3. **非装配文档无 asm**：fallback 现平文本路径（不影响，兼容）。
4. **G19a chapter 不存在**（某文档无工艺流程图）：skeleton 空 → _extract_triples_from_substeps 退化为不绑 process（build 不建 proc→spec 边，向后兼容）。

## 复用现有实现
- `extract_assembly_steps`（hierarchical_context.py:1784）：G25a 表格→asm（已处理 colspan）
- `extract_process_steps`：G19a→skeleton 真工序名
- `qty_patterns`/`spec_patterns`（document_profile_learner.py）：substep.content 上复用
- `merge_from`/`_safe_id`（knowledge_graph.py）：proc→spec 边跨文件汇聚
- `expand_context` BFS 2 跳：工序 seed 第一跳到规格
