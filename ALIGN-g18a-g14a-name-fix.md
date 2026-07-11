# 需求对齐卡：G18a/G14a 列表表名称用 extract 配对（消除 derive 倒推错位+待补）

> slug: `g18a-g14a-name-fix` · 承接 Web 端验收（2026-07-11）发现 · 软，可改，不 seal

## 背景（诊断已查实）

Web 端验收 project=2 生成发现：G18a 配套明细表 / G14a 辅助材料表生成时**代号-名称错位 + 大面积"待补"**。

- **extract 层达标**：`material_catalog` 表 62 行，代号-名称配对完整准确（KA6-20-KZD=尾焰挡板组件 / QJ2963.3-97=弹簧垫圈4 / KA6-0-KZD=六舱 等，source-driven-fix 的 `extract_and_save` 正确）
- **bug 在 derive/生成填充层**：G18a/G14a 走 derive-strong-node 的"从 G25a 倒推"路径（见 `PLAN-derive-strong-node.md`），该路径**未使用 material_catalog**，而是从 G25a content 倒推零件 + 推不了的字段标"待补"。后果：
  - **代号-名称错位**（KA6-0-KZD 生成"行程延时开关组合"，material_catalog 实为"六舱"；AKJ02-1A 生成"密封圈2"，实为"数据链射频前端"）
  - **可填却待补**（KA6-20-KZD 待补，但 material_catalog 有"尾焰挡板组件"）
- **G25a/G22a 正文表不受影响**（验收通过：5 工序+5 检验行，内容 AVG187/MAX981 字零臆造）

## 目标

- **解决谁的问题**：G18a 配套明细表 / G14a 辅助材料表代号-名称错位 + 名称待补，导致这两张表不可信
- **成功长什么样**（可观察）：重跑 project=2 生成，G18a 每行 part_name = material_catalog 中对应 part_code 的 name（KA6-20-KZD→尾焰挡板组件、KA6-0-KZD→六舱、AKJ02-1A→数据链射频前端），**无错位**；material_catalog 有名称的行**不再出现"待补"**

## 边界

- **做**：G18a/G14a derive/填充时**优先查 material_catalog**（extract 已 extract 的代号-名称配对）填 part_name，减少对 G25a 倒推的依赖
- **不做**：
  - 不动 extract 层（达标）
  - 不动 G25a/G22a/G19a（验收通过 / derive-strong-node 禁区：G19a 隔离不动）
  - 不重写 derive-strong-node 架构（最小改动：列表表填充引入 material_catalog 查询，不推倒倒推逻辑）
  - 不消除"设计性待补"（derive 真推不了的批量/来源/数量等字段，保留"待补"防臆造）—— 只修"material_catalog 有名称却没填上"的待补

## 模糊点（进 PlanMode 探索确认）

- G18a part_code/part_name 实际填充代码位置 + 数据流（orchestrator 倒推强节点 / `_derive_list_from_upstream` / structured 直填？）—— PlanMode 定位
- 代号-名称错位精确机制（代号、名称分别从哪来，如何错位 zip）—— PlanMode 读代码
- `material_catalog.standard_code` ↔ G18a `part_code` 匹配键 + code=None 行（只 name，如辅料/工具）如何处理 —— PlanMode
- G14a 辅料是否同根因（大概率同，PlanMode 验证填充路径）
- 修复落点：在 derive 倒推前/后插 material_catalog 查询，还是改 `_derive_list_from_upstream` —— PlanMode 定方案

## 下游

- → 进 PLAN（同 slug `g18a-g14a-name-fix`）
