# 需求对齐卡：G25a 装配工艺卡片「工序内容」撰写机制

## 目标
- 解决谁的问题：生成装配工艺规程时，G25a 装配工艺卡片的「工序内容(content)」当前为空，无法输出可用的工艺卡片。
- 成功长什么样：
  1. G25a 每道工序的 content 非空、含详细操作（1.1/1.2 工步展开），web 实测稳定生成（非偶发）
  2. 力矩等关键参数有来源：工步原文优先，画像 triples 兜底，不臆造
  3. 术语/数据/结构受画像两层约束：principles（强约束）+ preferences/writing（偏好）
  4. G22a 工序内容简述直填改动一并验证落地

## 边界
- 做：
  - 修 G25a content 空（让生成稳定出内容——定位并修 orchestrator 注入断点）
  - 接入画像两层约束到 G25a 写作 prompt：principles（术语一致/数据可验证/章节完整）+ preferences/writing（偏好）
  - 接入画像 triples 参考值兜底（工步原文缺力矩等参数时，从已验证三元组取值）
  - 顺带验证 G22a 直填改动落地（06-18 未提交）+ commit 清理起点
- 不做：
  - 不引入外部标准文件（QJ903 等）（用户选「按画像来」）
  - 不动 G19a skeleton 顺序（10 vs 12 步不一致，另案）
  - 不重写生成架构（source-driven 链路已成型，只补注入断点）
  - 不做测试体系/覆盖率（PMF 阶段）

## 模糊点
- [接受的不确定性] G25a content 空的精确断点：已定位到「phased 模式 G25a assembly_steps 注入（orchestrator:2607-2636）依赖 missing_chapters._doc_dir，正常生成时 G25a 可能不在 missing_chapters → 注入被 skip → is_g25a_sourced=False → 退化走普通 LLM 路径 content 弱/空」。read-only 无法完全实证（需跑生成看 stdout 日志），留执行 loop 第一节点动态验证 + 修复。
- [已澄清] 行文标准 = 画像两层（强约束 principles + 偏好 preferences），不引入外部标准文件
- [已澄清] 参数参考值 = 画像 triples 兜底（只取确实有的，不编）
- [已澄清] 现状 = content 没内容（当前就空，非偶发）

## 下游
- → 进 PLAN（同 slug：g25a-write）

## 现状诊断依据（2026-06-19）
- `verify_g25a.py` 实证：material id=1 装配工艺卡片 extract_assembly_steps 正常返回 10 工序 / 52 substeps（辅材/仪器齐全）→ 素材抽取层健康
- `writing_agent.is_g25a_sourced`：注入 g25a_source_block（工步原文）作 content 唯一事实来源 + 「禁止臆造」约束 → 逻辑存在，但前置（orchestrator 注入）可能没走到
- 画像 `assembly.json`：principles（3 条：章节完整性/数据可验证性/术语一致性）+ triples（力矩三元组：螺钉安装→1.9N·m 等）+ preferences/writing → 现成资源，未接入写作 prompt（只接入 review）
