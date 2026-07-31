# PLAN: 框选修改并入对话（UI/端点/SSE 统一）

> slug: `unify-selection-into-dialog`（`dialog-task-pipeline` 延伸）
> seal 后不可变。

## Context（为什么）
两套独立 AI 交互：①框选修改（`useSelection`→`AIContextMenu`→`useAIStream`→`/api/assistant/quick-actions-stream`）②对话（`AIChatPanel`→`/api/agent/generate-stream`）。用户要统一：浮菜单废弃，框选并入对话，UI/端点/SSE 一套。

硬约束：不动 generate-stream 主链；框选改写功能不丢（迁移到对话）。

## 方案（B:UI 也统一）
选区→AIChatPanel(selectedText)→quick-action 按钮→generate-stream(quick_action 分支,process_intent 前短路)→SSE content 回写编辑器(替换选区)。废弃 AIContextMenu/useAIStream/quick-actions-stream。渐进:先并入共存,后废弃。

## 改动清单
### 后端 agent.py
- generate-stream 加 quick_action 分支(接 selected_text+quick_action→ACTION_PROMPTS LLM 流式→SSE content;process_intent 前短路,主链保护)
- ACTION_PROMPTS 从 assistant.py 迁/复用

### 前端 AIChatPanel.tsx
- selectedText prop(:23)非空→quick-action 按钮(重写/润色/扩展)
- handleQuickAction(action):fetch generate-stream(selected_text+quick_action)→SSE content→回写编辑器(替换选区)

### 前端废弃(第二步,共存验证后)
- AIContextMenu 废弃、useAIStream 废弃、useSelection 保留
- assistant.py quick-actions-stream 降级保留,稳定后废弃

## 禁区
- generate-stream generate/fill/draft_complete/source-driven 主链零改动。
- 框选改写不丢。审校/QA/意图不动。

## 验证
1. 框选→AIChatPanel quick-action→重写→选区替换(同旧浮菜单)。
2. quick_action 分支不走 process_intent(主链不受影响)。
3. 回归 generate/fill/审校/QA/意图。4. tsc 0 错 + pytest。5. 旧浮菜单废弃后只一套。

## 下游
统一完成,经验回流(追加 exp-dialog-task-pipeline)。
