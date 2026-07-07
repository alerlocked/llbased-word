# PLAN: 撤 standard-enforce + 建反馈规则学习闭环

> slug: `feedback-rules` | 项目: localknowledgebase-word | seal: 2026-07-08
> 承接对齐卡 `ALIGN-feedback-rules.md`。seal 后不可变，进度记 DEV-LOG/git。

## Context

standard-enforce（2026-07-06 commit `5f8321f` 标准注入 + `45027be` review 校验）经实测是错配：QJ903 标准库 38 条全是前言废话、safety=0、LIKE 对"螺栓/焊接/检验"召回 0 → 注入的是噪声、校验判不出真违规，功能空转且污染生成。

"装配工艺怎么算准"没有现成标准可编码（QJ903 是文件管理标准，非工艺参数标准）。改为**从用户对生成结果的修改中学习**（Cursor rules/memories 范式：可读可改的规则文本 + 显式注入）。

本 PLAN：撤 standard-enforce 噪声 + 建「编辑 diff → LLM 归纳成 principle → 待审启用 → 注入下次生成」的轻量闭环，**复用现有 profile.principles 机制**，不另起炉灶。

**成功标准**：① 撤除后 system_msg 无标准条款段；② 用户改→保存→归纳出候选规则（enabled=false 待审）；③ UI 审启用 → 再生成注入该规则；④ 规则全程可读可改。

## 改动清单

### 节点1 — 撤 standard-enforce（纯减法，先建干净基线）
- `backend/app/agents/functional/writing_agent.py`：删 1025-1056（标准条款注入 try/except 段）。保留 1003-1024 principles/triples 注入 + 1058+ G25a gate
- `backend/app/services/review_service.py`：删 review() 内调用（108-110）+ `_check_standards` 方法（158-208）。**保留 `async def review(..., skip_standard_check=False)` 签名**（调用方 review_agent.py:156 已 await，零改动）
- `backend/tests/test_review_service.py`：删 10 处 `skip_standard_check=True` 传参，保留 async 测试签名

### 节点3 — 后端 FeedbackLearner + API
- **新建 `backend/app/services/feedback_learner.py`**：`FeedbackLearner.learn_from_edits(edits, row_changes, domain, project_id, skip_llm)` async
  - LLM 归纳 prompt：输入 cell diff（"章节X/行Y/列Z: 「旧」→「新」"），输出 `{rules:[{dimension,name,description,check_expression}]}`，只归纳可复用规则（如 5 处"力矩→扭矩"→ 一条术语统一规则），不逐条复述
  - fail-soft 三层：LLM 失败 → `_rule_based_fallback`（同 col_key 重复 old→new 产 terminology 规则，保证测试可断言）→ 异常返 `[]`
  - 产 `Principle(source="feedback_learned", enabled=False)`（待审，不自动污染生成）
- `backend/app/api/profile.py`：
  - 加 `LearnFeedbackRequest` / `CellEditItem` / `RowChangeItem`（edits/row_changes/`project_id: str`/skip_llm）
  - 加 `POST /{domain}/learn-feedback`：调 FeedbackLearner → 循环 `profile.add_principle`（复用 name+dimension 去重）→ 返回新增规则
  - 加 `PATCH /{domain}/principles/{principle_id}`（改 enabled/description/name）—— 审查 UI 需要，现有只有 POST(311)+DELETE(327)
- **新建 `backend/tests/test_feedback_learner.py`**：skip_llm=True fallback 断言 + edits 空→`[]` + LLM mock 非法 JSON→`[]`

### 节点4a — 前端原始快照
- `frontend/src/stores/creationStore.ts`：加 `originalTemplateData: TemplateSection[] | null` + setter（持久化 localStorage）
- `frontend/src/pages/AIChatPanel.tsx:687`：生成接收时把 `data.template_data`（StructuredDocument）转成 `TemplateSection[]` 存进 originalTemplateData
- **复用** `WorkspacePage.tsx:69` 的 StructuredDocument→TemplateSection[] 转换，抽成 `frontend/src/utils/templateTransform.ts`（AIChatPanel + WorkspacePage 共用，不重写）

### 节点4b — 前端 diff 采集
- `frontend/src/pages/WorkspacePage.tsx:319`（handleSave）：算 diff 后静默 POST `/api/profile/{domain}/learn-feedback`，fail-soft（失败不打断保存）。基准恒定 = originalTemplateData
- **新建 `frontend/src/utils/templateDiff.ts`**：
  - 行对齐：同 section_id 下用业务键（序号/工序号/step_no）配对；无键退化按 index（仅行数相同 section 做 cell-diff，避免行增删错位噪声）
  - 两类输出：`edits[]`（section_id/row_key/col_key/old_value/new_value，全 stringify）+ `row_changes[]`（added/removed + 整行）

### 节点5 — 前端规则审查 UI
- 新建规则审查页/面板（复用 `GET /api/profile/{domain}`）：按 `source` 分组（builtin/manual/feedback_learned），feedback_learned **置顶** + "从你 N 处修改归纳出 M 条候选"提示
- 每条：启用/禁用 + 编辑 + 删除（用节点3 PATCH + 现有 DELETE）
- `profile.py get_default_assembly_profile` 内置 3 条 principle 补 `source="builtin"`（便于分组，1 行级）

### 节点6 — 端到端验证
- 生成→改几个 cell→保存→审查页出现候选（enabled=false）→启用→再生成→grep 后端日志确认 system_msg 含该规则
- pytest 全量回归

## 禁区
- 不碰 specialty 生成路由 / 机加焊接模板（远期多专业）
- 不碰 G25a gate（1058+）、principles/triples 注入段（1003-1024）
- 不改 review async 签名（保留 async + skip_standard_check 参数）
- 不引入 ML 训练 / 向量记忆（纯 case 堆已否决）
- FeedbackLearner 不直接写 profile JSON，走 `profile.add_principle` + 现有 `_save_profile`

## 关键复用（不另起炉灶）
- `profile.add_principle`（profile.py:339）name+dimension 去重 → 幂等
- `Principle.source` 字段（profile.py:97）→ 来源区分，不改 dataclass
- principles 注入（writing_agent.py:1003-1024）→ enabled=true 自动注入，feedback_learned 启用后自动生效
- `WorkspacePage.tsx:69` StructuredDocument→TemplateSection[] 转换 → 抽 util 复用
- `learn_from_content`（document_profile_learner.py）async + skip_llm + fail-soft 模式 → FeedbackLearner 类比
- `llm_service.generate_with_messages(tier="simple")` + review_service.py:192 JSON 抓取模式

## 验证
- 节点1：`grep -rn "standard_inject_failed\|适用标准条款" backend/app/agents/functional/writing_agent.py`（应空）；`pytest backend/tests/test_review_service.py -v`
- 节点3：`pytest backend/tests/test_feedback_learner.py -v`；curl POST learn-feedback（skip_llm=true）→ 查 `backend/data/profiles/assembly.json` 多 source=feedback_learned/enabled=false 规则
- 节点4a/4b：`cd frontend && npx tsc --noEmit`；`npm run dev` 冒烟：生成→改 cell→保存→Network 看 POST learn-feedback 含 edits[]
- 节点5：tsc + 冒烟：审查页 3 分组、PATCH 启用生效
- 节点6：端到端闭环 + `pytest backend/tests/test_review_service.py backend/tests/test_feedback_learner.py -v`

## 约束（pitfalls）
- T01 删除清三层 / T02 禁跨层路径 / commit 前查暂存区 / 前端 ID 按字符串（int64 丢精度）/ sync→async 改造同步调用方+测试（本 PLAN 保留 async 不改调用方）/ fail-soft 不阻塞保存

## 执行顺序
1 → 3 → 4a → 4b → 5 → 6（后端先就位，前端逐步接；1 与 3 独立可并行起手）
