# 需求对齐卡:对话任务管道完善 + 意图收敛

> slug: `dialog-task-pipeline`(总纲,延续)。第一轮(2026-07-30)done 4 块(死代码清理/审校对话/QA 提质/意图识别 LLM 化);第二轮(2026-08-11)收敛意图 + 补 edit_local + unify 选区 + 计划确认 + 素材检查。
> 现状据代码实测,见文末「现状证据」。

## 目标
工艺人员对话下任务 → 系统可靠识别意图 → 走对链路跑通。把对话交互链路补全到 5 个意图全覆盖,每个意图落到正确的基础能力组合(不悬空、不语义错配)。

## 决策(2026-08-11 第二轮对齐,模糊点已清零)

### D1. 意图集 10 → 5(第一性原理:意图=入口路由,功能=基础能力组合)

| 意图 | 入口 | = 基础能力 |
|------|------|-----------|
| 生成/补齐(合并 create/generate/draft_complete) | 🟢 独立按钮工作流 | writing(source-driven)+检索 |
| 改动 edit_local | 🔵 对话路由 | 定位+改(执行单元待建) |
| 审查 review | 🔵 路由 / 快捷按钮 | review + compliance 检索 |
| 校对 proofread | 🔵 路由 / 快捷按钮 | proofread + terminology tool |
| 问答 qa | 🔵 对话路由 | 检索 + 问答 |

**删/不进对话**:解析PDF(上传触发,非对话意图) / 导出PDM(跳过,无实现) / 对齐术语(降 tool) / 查合规(review 内检索,不独立) / 搜知识(qa 内检索,不独立)。

### D2. 两类入口架构
- 🟢 **生成/补齐 = 独立按钮 + 完整工作流**:source-driven 生成 + **素材完整性检查(防臆造硬约束)**——素材不全 → INFO_ASSESSMENT 追问让用户补,有大致内容才能生成,绝不胡诌。可带初始文档也可不带。
- 🔵 **改动/审/校/问答 = 对话意图路由**:意图识别 → **出计划清单给用户确认** → 链路执行。
- 审/校按钮 = 快捷触发 review/proofread 意图的入口(**保留**,底层统一走路由)。

### D3. unify 选区(Cursor 式)
删浮菜单 `AIContextMenu` + 删 `quick_action` 分支(`agent.py:909`);选区 → 贴入按钮 → 对话框上方引用标签(小括号标注内容 + ×)→ 选区并入对话上下文让模型读。

### D4. edit_local(改动,高频)
生成完就要改,高频。先 **B1 cell/值级**(定位 章节+行+列 → 改单值 → 回传前端表格),B2 整段改视效果再议。⚠ 进 PLAN 前确认改的对象(已生成表格 cell vs free-form 文本)。

## 边界
**硬约束**:① 不动 generate/fill 主链(generation_mode shortcut → draft_complete → source-driven) ② 增量改,不重写活链路 ③ 防臆造(生成必须基于素材,素材不全追问补全)

**做**(待拆 PLAN,从简到难,一块一个):
1. **unify**(D3)——PLAN `6141ac2` 已 seal,UI 变需重新 seal
2. **意图收敛**(D1)——IntentType 枚举 + INTENT_TO_TASKS + agent_mapping 三处对齐
3. **edit_local 执行单元**(D4,最复杂)
4. **计划确认交互**(D2)——意图 → 出计划 → 用户确认 → 执行
5. **素材检查追问**(D2)——生成/补齐 INFO_ASSESSMENT 强化

**不做**:❌ 向量检索/SearchAgent ❌ 重写 source-driven 生成主链 ❌ 解析PDF/导出PDM 进对话意图

## 下游
按"做"顺序一块一块走,每块独立 PLAN + 验证 + commit。**第一块 = unify**。

---
## 现状证据(代码实测 2026-08-11)
- **前端**:`AIChatPanel.tsx` 有 generate/fill/审/校 按钮 + 输入框;`AIContextMenu`(浮菜单)+`useSelection`+`useAIStream` 仍活(走旧 `/api/assistant/quick-actions-stream`);`AIChatPanel.tsx:24` 有 selectedText prop 但无引用标签 UI。
- **后端意图识别**:`intent_recognizer.py` 10 类 IntentType(LLM 分类 `_classify_with_llm:135`,fail-soft 关键词兜底)。
- **后端调度**:`process_intent` generation_mode shortcut → draft_complete 主链(活);`task_decomposer.INTENT_TO_TASKS` 模板化(EDIT_DOCUMENT → pdf_parsing/data_validation/compliance_check/user_confirmation);`_dispatch_to_sub_agent` `agent_mapping`(`orchestrator.py:681`)已补全(document_generation→writing, data_validation→proofread, compliance_check→review, terminology_alignment→proofread)。
- **edit_document 语义错配**(P0):识别✓,但 decompose 跑成 proofread+review,**无"定位+改+回传"执行单元**;writing 虽接 edit(`:683`)但 EDIT_DOCUMENT 不产出 edit task。
- **quick_action 分支**(`agent.py:909`):框选改写固定动作,待删(D3)。
- **functional agent**:review/proofread 活,registry 注册。
