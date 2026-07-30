# PLAN: 对话式审/校链路（复用现有 review/proofread 端点 + 前端按钮接线）

> slug: `dialog-review-proofread`（总纲 `dialog-task-pipeline` 第二步）
> seal 后不可变。Reviewer 从 git 读本文件。

## Context（为什么）
对话任务分配链路断裂诊断发现:**审/校无前端入口**——后端 functional agent review/proofread + `/api/tasks/review` 端点都活着,只差接线。这是总纲第二步:让用户在 AIChatPanel 点「审查/校对」按钮,对当前编辑器里的工艺文件做审查/校对,问题清单(issues)回前端渲染。

**硬约束**:不动 generate-stream / draft_complete / source-driven 生成主链;基于现有功能。后端 review/proofread 链路完整(ReviewAgent/ProofreadAgent + ReviewService 含 specialty-rules 敏感词/必填参数校验 + `/api/tasks/review`(task.py:567) + `/api/tasks/proofread`(task.py:530) 同步端点 + `orchestrator.review_only()`/`proofread_only()` 活方法),**本期只做前端接线 + 结果渲染,后端复用(零或微调)**。

## 方案
- **后端复用现有同步端点**(`/api/tasks/review` + `/api/tasks/proofread`),不新建 SSE、不动 generate-stream。审查/校对是秒级 LLM 校验,同步 fetch 够用;后续体验不够再升级 SSE。
- **前端**:加「审查」「校对」按钮 → 取当前编辑器内容 → 同步 fetch → 渲染 issues 列表。
- **入口**:按钮(显式传 mode),对齐 generate/fill。自然语言触发留第三步(意图识别改 LLM)。

## 改动清单

### 前端(主 `frontend/src/components/AICreation/AIChatPanel.tsx`)
| 改动 | 说明 |
|------|------|
| 加「审查」「校对」按钮 | 照 generate/fill toggle 模式(:1253-1293),新 mode state(`review`/`proofread`),互斥高亮;4 按钮挤则分两行 |
| 取编辑器内容 | 点击时从 `creationStore.getProjectState(projectId)` 取 `editorTemplateData`(序列化成文本,优先)或 `editorContent`,作为审查 `content` |
| 序列化 | 复用现成 `templateTransform.ts`/`structuredDocToSections` 把 template_data → 文本;无则写最小序列化(章节名+单元格值) |
| fetch `/api/tasks/review` 或 `/proofread` | 同步 POST,body `{content, check_type:'all', domain, standards?}`;`domain` 从 `localStorage.profile_default_${projectId}`(对齐 generate-stream body :510) |
| 解析响应 | `AgentResultResponse.result.issues`(severity/type/message/fix_hint)+ `passed` |
| 渲染 issues | 新增 `ReviewResultPanel`(复用 `improvementSolutions`/`SolutionList` 渲染模式),消息区渲染:severity 分级(error红/warning黄/info蓝)+ message + fix_hint |

### 后端(预期零改动,执行时确认)
- 复用 `/api/tasks/review`(task.py:567)+ `/api/tasks/proofread`(task.py:530)。仅当响应字段前端不便解析或 content 序列化需后端配合时,做最小适配。

## 禁区
- `generate-stream`(agent.py:853)/ `draft_complete` / `_handle_draft_complete` / source-driven 生成主链:**零改动**。
- `intent_recognizer` / `detect_mode`:不动(第三步)。
- `ReviewService` / functional agent 内部逻辑:不动(复用)。

## 验证
1. 起后端 + 前端,generate 一份工艺文件。
2. 点「审查」→ fetch `/api/tasks/review`(content=编辑器内容、domain 对)→ issues 渲染(severity 分级 + fix_hint)。
3. 点「校对」→ `/api/tasks/proofread`。
4. 构造含敏感词(「适量」)或缺必填参数 content → 确认 `sensitive_word`/`missing_mandatory_param`(specialty-rules 生效)。
5. **回归**:generate/fill 补齐主链不受影响。
6. `tsc` 0 错 + `pytest` 回归(后端零改动应 762 passed)。

## 下游
验证通过 + commit 后,回总纲对齐第三步。
