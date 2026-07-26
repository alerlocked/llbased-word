# PLAN: G25a/G18a 生成质量修复（3 bug）

> slug: `g25a-g18a-quality` | ALIGN: `ALIGN-g25a-g18a-quality.md` | seal 后不可变

## Context（为什么改）
2026-07-26 用户测试（str>int 修后前端能显示）发现 3 个内容质量问题：
1. **G25a 工步漏**：装配卡工序7 从 7.5 开始，漏 7.1–7.4。documents/1 工序7 extract 不漏，用户素材漏 = `extract_assembly_steps` 跨页/续页丢 substep（candidate C：`_PARTS_LIST_MARKERS` 在续页元信息误触发 `in_parts_list=True` 跨续页未复位，吞掉 substep）。
2. **G25a 工序名称填"钳"**（工种）：`writing_agent:851` 用 `asm.name`；skeleton 有真工序名没用。
3. **G18a source 列"工艺流程图"**：derive 倒推串源。源表真实 source"火工库"（已查证），但 G18a 没 extractor，derive LLM 反推误填。

## 改动清单

| 文件 | 改什么 |
|---|---|
| `backend/app/services/hierarchical_context.py` | **N1** `extract_assembly_steps` :1836-1842 续页表头判定分支补 `in_parts_list=False`；`_PARTS_LIST_MARKERS`(:79) 收紧（同行 ≥2 marker 或含"代号"+"名称"，防续页元信息误触发） |
| `backend/app/agents/functional/writing_agent.py` | **N2** :851 `step_name` 改用 `skel[k-1]`（真工序名，越界回退 asm.name）+ 改 :846-850 注释；**N3** :1349 `fill_cols` 构造后加 `if chapter_code=="G18a": fill_cols=[c for c in fill_cols if c.key!="source"]`（G18a source 列跳 derive，走"待补"兜底） |
| `backend/tests/` | N1-N3 单测（extract 跨页 in_parts_list 复位 / step_name=skeleton / G18a source 不进 derive） |

## 禁区
- 不改 craft-kg-quality 已 commit 代码
- 不臆造工时定额（设计性留）/ G14a 留（源少）
- 不写 G18a extractor（方案 B 留 TODO，本次方案 A 止血）

## 节点顺序（每节点 1 commit）
N1（Bug1 extract 续页复位 + markers 收紧）→ N2（Bug2 step_name=skel）→ N3（Bug3 G18a source 跳 derive）→ N4（端到端验证）。

## 验证
- 单测：extract 跨页 in_parts_list 复位（续页表头+marker 行→substep 不丢）+ step_name=skeleton + G18a source 不进 derive
- 全量 pytest 0 新 fail（基线 701）
- 端到端（云端 qwen3 + documents/1 不回归）：G25a 工序名=真名 + 工序7 substep 还全 + G18a source≠"工艺流程图"
- ⚠️ Bug1 用户素材效果（工序7 出 7.1-7.4）待用户验

## 风险
1. Bug1 candidate C 假设（documents/1 不触发不漏，用户素材漏；修复预防性，用户素材效果待验；复位+收紧无害不回归）
2. Bug3 方案 A 填"待补"（非真实"火工库"，方案 B 留 TODO）

## 复用
- `skel`（writing_agent:842 取、:856 用于内容块）→ Bug2 直接用
- `_merge_derived_rows`"待补"兜底 → Bug3 方案 A
- `extract_doc_catalog`（:1716）按列名抽取范式 → 方案 B（TODO）参照
