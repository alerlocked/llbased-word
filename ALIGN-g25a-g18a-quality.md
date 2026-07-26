# 需求对齐卡：G25a/G18a 生成质量修复

## 背景（为什么做）
2026-07-26 用户测试发现 3 个生成质量问题（str>int 修复后前端能显示，但内容不齐）：
1. **G25a 装配卡工步漏**：工序7 从 7.5 开始写，漏 7.1–7.4（documents/1 工序7 extract 不漏，用户素材漏 = extract 跨页/colspan 丢 substep，extract 阶段就缺，不是生成漏）
2. **G25a 工序名称列填"钳"**：`writing_agent:851` 把 `asm.name`（工种）填进工序名称列；但 skeleton 有真工序名（装前准备/安装密封圈2/...），没用
3. **G18a 配套表 source 列填"工艺流程图"**：derive 倒推串源——配套零件清单不在工艺流程图（流程图是工序流程），source 列误填

## 目标
修这 3 个，让装配卡工序内容完整 + 工序名称正确 + 配套表 source 不串源。

## 成功标准（可观察）
- G25a 跨页工序的 substep 不丢（用户素材工序7 出现 7.1–7.4，documents/1 不回归）
- G25a 工序名称列填真工序名（装前准备/安装密封圈2/...），不再全"钳"
- G18a source 列不填"工艺流程图"（填真实来源 或 空，不串源）
- 不回归：全量 pytest 0 新 fail

## 边界
### 做
- G25a `extract_assembly_steps` 跨页 substep 拼接（同一工序跨多页时 substep 不丢）
- G25a 工序名称填 skeleton 真工序名（`writing_agent:851`）
- G18a source 列 derive 串源修复
### 不做
- G14a（源 263 字符，定额设计性，留）
- 工时定额（源空设计性，不臆造，留）
- 不改 craft-kg-quality 已 commit 代码
- 不臆造数据

## 模糊点（进 PlanMode 清零）
1. **G25a extract 跨页**：当前 extract 每页独立解析？跨页工序的 substep 怎么拼（前一页尾 + 后一页头同属一工序）？colspan 错位导致 substep 丢？
2. **G18a source**：derive 倒推 source 该填啥？配套零件真实来源是哪里（配套明细表自身的"来自何处"列 / G25a 装配卡 / 空）？"工艺流程图"是 derive 默认值还是源表格内容？
3. **G25a 工序名 skeleton 对齐**：skeleton[i]=G25a step i+1（craft-kg-quality 验过），直接用 skeleton[i]

## 下游
- → PLAN（同 slug `g25a-g18a-quality`）
