# PLAN: 生成前数据源门控（source-gate）

## 改动清单

| # | 文件 | 改什么 |
|---|------|--------|
| N1 | `backend/app/agents/orchestrator/orchestrator.py`（~2108） | requires_response 返回的 missing_chapters 条目透传 `_doc_dir` |
| N2 | `backend/app/api/agent.py`（请求模型 + requires_response 分支） | 加 `confirmed_missing` 字段；有无源章节且未确认 → 如实分栏报告 + confirm_request 事件 → return（不调 continue_conversation）；无源=空或已确认 → 现行直通 |
| N3 | `orchestrator.py`（task 装配）+ `writing_agent.py`（路由） | 无源章节 task 打 `source_missing`（仅该 task 不 fallback draft_content）；writing_agent 早退构造全槽"待补"占位，零 LLM |
| N4 | `frontend/src/components/AICreation/AIChatPanel.tsx` | confirm_request → 确认卡片（无源清单+继续/取消）；继续=缓存 body+confirmed_missing 重发 |
| N5 | ARCHITECTURE + DEV-LOG + 三路回归 | 齐全直通 / 缺源停+确认待补 / 全缺源 |

## 禁区

- 状态机结构、检索/注入/骨架链路、hierarchical_context.py、画像、_do_template_fill 主体
- 数据源齐全场景行为 diff 为零（回归红线）

## 验证

- 单测：_doc_dir 透传；source_missing → 待补 + LLM 未调用
- curl 三路（confirm_request 即止 / confirmed 生成待补 / 齐全直通）
- Playwright 前端卡片交互；tsc 0 错；全量 pytest 零回归

## 已知边界（不修，记 DEV-LOG）

- _doc_dir 非空但抽取文本空 = 有源直通（现行行为）
- 空工作区 generate = 全部无源，卡片明示
