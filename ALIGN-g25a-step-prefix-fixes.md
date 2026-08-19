# 需求对齐卡：G25a 三缺陷修复（工序名前置直拼 / 工序8无编号引子 / skeleton 噪声）

> 来源：2026-08-18 用户实测报告（TODO 3c，修法用户已拍板）；交接卡 task_slug 同名。

## 目标

- 解决谁的什么问题：工艺人员看 G25a 装配卡生成结果，每道工序开头缺工序名总起句、工序8 缺 8.1/8.2、G19a 骨架混入签名区/页脚噪声——不像真实工艺文件。
- 成功长什么样（可观察）：
  1. 每道工序 content 第一行 = `工序名：`（程序化前置，不依赖 LLM 自觉；降级直填路径同样带）
  2. 工序8 类「开头无编号引子段」被并入首工步，不再挤占 8.1/8.2 编号；不丢引子信息
  3. `extract_process_steps` 骨架不再出现「阶段标记/更改标记/共N页/第N页」
  4. 单测复现三缺陷→转绿 + 全量 pytest 0 回归（基线 853 passed）

## 边界

- 做：
  - ① `writing_agent.py` gen_one：content 编号后处理后程序化前置 `f"{name}：\n"`（`skel[i-1]` G19a 真工序名，name 非空才拼）；`_fallback_slots` 降级路径同拼；prompt 约束3 改「不要写总起句，系统已前置工序名」；防重复——拼接前 strip 掉 LLM 可能仍写的行首 `{name}[：:]`（exp-g25a-step-numbering：prompt 拉不住，程序化兜底）
  - ② `hierarchical_context.py` `extract_assembly_steps` 后处理：每道工序**开头连续的无 N.M 编号行**（含折行断句）并入首个带编号工步 content 头，不独立成步；整道工序无编号工步时保持现状（全是真实内容）
  - ③ `extract_process_steps` 过滤补 `阶段标记/更改标记` + `共N页/第N页` 模式
  - ARCHITECTURE.md 同步（架构层 PR 强制）
  - 测试：`tests/test_hierarchical_context.py`（②③ fixture 用真实片段复现）+ `tests/test_writing_agent*.py`（①）
- 不做（显式挡 scope creep）：
  - 6cbaf30 F2 状态块注入 A/B（交接卡：3c 修完生成效果仍差才回查）
  - 意图路由两病灶 / edit_local（TODO 3b，等 PR #63 合入）
  - PR #63 复验（pr-watch 自动轮询，不占本线）
  - `tests/fixtures/exports/` 测试输出垃圾清理（另项处理，不混进架构 PR 污染 diff）
  - 真实重生成的 web 端验收若本机不可行 → 留用户部署环境验

## 模糊点

- ~~修法是否需要再确认~~ —— ①②③ 修法 2026-08-18 用户已拍板（TODO 3c 原文），无字段语义歧义（`skel` = G19a 真工序名已实证，exp-g25a-g18a-quality Bug2）→ 已澄清
- 验收深度：单测 + 全量回归为硬标准；真实 LLM 重生成 G25a 冒烟**尽力跑**（本机云端 LLM 可达则跑，不可达不阻塞）→ 接受的不确定性
- PR 流程：①②③ 全动架构层文件（`agents/**` + `hierarchical_context.py`）→ 单一 `feature/arch-*` 分支 + `[architecture]` PR（CONTRIBUTING §4）→ 已澄清

## 下游

- → 进 PLAN（同 slug `g25a-step-prefix-fixes`）
