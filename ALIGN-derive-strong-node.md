# 需求对齐卡：倒推强节点（工艺链路配套关系补齐）

> slug: `derive-strong-node`
> 关联调研：3 份 agent 调研（知识库架构 / writing+G19a / 模板+倒推可行性），已落 NTM-wiki exp 页（[[exp-test-baseline-cleanup]] 同期）
> 关联经验页：[[exp-generation-debugging]]、[[exp-docx2pdf-chinese-path]]

## 目标

- **解决谁的什么问题**：当前明细表/配套表（G10a/B12a/G12a/G14a/G18a/G5a）补不齐——`_derive_list_from_upstream` 是「残缺才跑」的弱兜底（structured 抽空 + LLM 空 + upstream 有，三空才触发），原文抽出残缺数据就跳过倒推，明细表只拿到原文有的部分。
- **成功长什么样**（可观察）：跑「G19a 流程图 → G25a 工艺内容 → 前置配套关系倒推」链路，对 `documents/1`（44 页真实规程）：
  1. 各明细表完整度提升（原文 structured + 倒推合并后行数 ≥ 原文单 source）
  2. 倒推条目可溯源到 G25a 某行（不臆造）
  3. 推不了的字段（净重/零件代号/批量/工时等）显式标「待补」，不是 LLM 编

## 边界

### 做
- `orchestrator.py:2791`（Phase 循环后、Review-Retry 前）插入**倒推强节点**
- `_derive_list_from_upstream` 升级：去「三空」门槛 + 字段边界声明（每张明细表显式声明哪些字段倒推得了 / 哪些推不了）
- **B12a 脱孤儿**：纳入强节点 + dual_list 分栏倒推（工具←instruments+content，量具←content 里量具词）
- **G18a 零件维度**：从 G25a content/references 提零件（非工序维度），不强行对齐工序数
- **原文优先合并**：原文 structured 抽到的 > 倒推的，倒推只补原文缺的，同条目去重
- **推不了标「待补」**：净重/材利用率/坯料/零件代号/来源/批量数/工时 → 值 = `"待补"`，绝不 LLM 编
- **溯源校验**：倒推条目必须能在 G25a 某行找到出处，否则丢弃

### 不做
- ❌ 知识库/向量检索改造（方案 1，下一轮）
- ❌ 画像治理（下一轮）
- ❌ 改 G19a/writing 主路径（只读依赖，不动 G19a 隔离）
- ❌ 改前端（后端产出对齐现有 `filled_data` / `left_data` / `right_data` 结构）
- ❌ 重写 `_derive_list_from_upstream`（复用 + 改触发/边界，不推倒）

## 模糊点（已清零，2026-07-05 对齐）

1. **强节点架构**：✅ **替换**（用户定）—— 移除 Phase 3 内 `_derive_list_from_upstream` 调用（`writing_agent.py:1161-1203`），倒推逻辑统一提到 `orchestrator.py:2791` 强节点。前提：确保改动无误（充分测试 + 溯源校验兜底）。
2. **「待补」格式**：✅ filled_data 单元格值 = `"待补"` 字符串（不改数据结构，零改前端）。
3. **溯源失败**：✅ **丢弃该条目**（用户定，防臆造优先，宁可少不可假）。
4. **测试验收**：✅ **行数对比 + 人工抽样 5-10 条**（用户定，验质量 + 验不臆造）。

→ 模糊点清零，进 PlanMode 写 PLAN。

## 下游

- → `PLAN-derive-strong-node.md`（同 slug，模糊点清零后进 PlanMode 写）
