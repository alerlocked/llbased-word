# 需求对齐卡：生成质量回归修复（空章节 + 过程卡退化 + 话术矛盾 + 记忆报错）

> slug: `gen-quality-fix` | 项目: localknowledgebase-word | 日期: 2026-07-09

## 背景

2026-07-08 feedback-rules 落地后，07-09 端到端生成暴露 4 个质量回归。pytest 全量 0 failed（674 passed / 6 xpassed / 0 failed），但**实际生成内容不可用**。日志铁证（`app_20260709.log` 20:05）：

- `derive_strong_failed: name 'TemplateColumn' is not defined` ×6 章节（G4a/G5a/G10a/G12a/G14a/G18a）
- `[记忆服务] 异步摘要保存失败: 'NoneType' object is not subscriptable`
- 话术「知识库暂无参考素材」与「已从知识库提取 10 章节」并存

## 目标

- **解决谁的什么问题**：工艺工程师生成装配工艺文件，本次出现「列表章节全空 + 工艺过程卡工序名丢失 + 助手话术自相矛盾 + 记忆服务报错」，生成结果不可用。
- **成功长什么样**（可观察）：
  1. G4a/G5a/G10a/G12a/G14a/G18a 列表章节不再全空——derive 强节点恢复，后端日志再无 `derive_strong_failed`
  2. G22a 工艺过程卡「工序内容简述」(step_desc) 恢复**直填工序名短词**（旧版行为，= exp-generation-debugging §1.1）
  3. 初稿分析报告不再自相矛盾——知识库有文档时不说「暂无参考素材」
  4. 记忆服务异步摘要不再报 `NoneType`
  5. pytest 全量回归 0 failed；diagnose_all_chapters 列表章节填充率回升

## 边界

**做**：
- 修 `derive_list_strong` 的 `TemplateColumn` 局部 import 缺失（让强节点能跑，**不改其 4 约束设计**：溯源/边界/原文优先/待补）
- 修 G22a step_desc 直填链路（恢复工序名短词）
- 修 `material_status` 话术/信号源（区分「素材库」vs「知识库文档」）
- 修记忆服务 `NoneType`

**不做**：
- 不改 derive 强节点 4 约束设计（exp-derive-strong-node 固化的好设计）
- 不重构生成主路径（G19a 先行 / G25a perstep 不动）
- 不做新功能 / 多专业扩展
- 不在本 lead 收 feedback-rules 节点6（修完重启后端可顺带验，但归属 feedback-rules）

## 模糊点

- [已澄清] **过程卡期望**：用户原话「工艺流程图每个工序名称直接放到工艺内容简述，够了，不要往下写」= exp §1.1 直填短词（装前准备/安装密封圈2），不展开 substeps
- [PLAN 探查] 过程卡**现状**为何退化（直填链路哪断了）→ PlanMode 只读定位，不影响对齐
- [PLAN 探查] `derive_list_strong` import 缺失是哪个 commit 引入的回归（git blame 07-05 derive-strong-node 之后：standard-enforce / profile-expand / feedback-rules）
- [接受的不确定性] 修 import 可能连带发现其他 derive 路径同类缺漏，PLAN 阶段一并修
- [已定] 验证：`diagnose_all_chapters.py`（conda `gywj`，exp 推荐可靠方式）为主 + pytest 全量 + 收尾 web 端到端

## 下游

→ 进 PLAN（同 slug `gen-quality-fix`）：PlanMode 只读探查 4 个根因代码现状 → 改动清单 → seal。
