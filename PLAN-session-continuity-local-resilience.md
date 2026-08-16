# PLAN: 会话接续 + 本地 LLM 韧性 + G25a 静默失败治理

## Context

localknowledgebase-word 进入多人协作 + 底层架构更新阶段（同事做登录/用户层）。本 slug 解决三个已对齐的问题（ALIGN-session-continuity-local-resilience，模糊点已全部清零）：

1. **会话接续缺失**：主生成链路不读会话记忆，前端只送 last-10×500 字，本地 Qwen3-30B-A3B 多轮修改上下文易满。方案（用户拍板）= state（项目级滚动工作状态）+ memory（会话摘要，按项目分目录）
2. **本地 LLM 错误裸抛**：llm_service `max_retries=1`，所有异常一锅端。方案 = 错误分类 + 重试退避 + 上下文溢出裁剪重试
3. **G25a 工序表部分行为空**（用户报告：工序四有/五空/六有）：根因代码级定位 = `writing_agent.py:1729/1736/1762` 三处单行失败静默 `return []`。方案 = 单行重试 + 完成度核对显式上报。违反 VISION「可靠」验收（不静默假成功）

分支 `feature/session-continuity-local-resilience`（已建），PR 流程合入，`/pr-review` 审查（agents/** 属架构层隔离，强制 review）。

## 改动清单（9 节点，每节点一 commit）

### 轨道一：LLM 韧性 → G25a 治理

| # | 文件 | 改什么 |
|---|------|--------|
| N1 | `backend/app/services/llm_errors.py`（新）+ `tests/test_llm_errors.py` | 错误分类模块：`LLMErrorClass` 枚举（TIMEOUT/CONNECTION_REFUSED/CONTEXT_OVERFLOW/EMPTY_REPLY/JSON_PARSE_FAIL/RATE_LIMIT/UNKNOWN）、`classify_exception()`、`classify_error_text()`、`USER_FACING_MESSAGES` 中文可读映射、`should_retry()`、`trim_messages_for_overflow()`（只裁最长 user 消息，不碰 system） |
| N2 | `backend/app/services/llm_service.py` + `tests/test_llm_service_resilience.py` | `generate_with_messages`/`generate_text` 内包 `_generate_with_retry`：1+2 次重试指数退避，CONTEXT_OVERFLOW 裁剪一次后重试，EMPTY_REPLY 重试一次；错误 dict 增量加 `error_class` 键（不动原 4 键契约）；structlog 风格日志（`llm_call_retry`/`llm_call_failed`） |
| N7 | `backend/app/agents/functional/writing_agent.py` + `tests/test_writing_agent_g25a_resilience.py` | `_generate_g25a_per_row_parallel`：`gen_one` 内重试循环（LLM error/parse fail 各退避重试 2 次，`g25a_per_step_retry` 日志带分类）；gather 后完成度核对（n 行 vs 有内容行），缺口 `g25a_completeness_gaps` 日志 + 返回值扩为 4 元组加 `row_gaps`；`_do_template_fill` 返回 dict 增量加 `warnings` 键（沿现有 structured_results 管道零改动穿透到 agent.py，已核实 orchestrator.py:3202 整体拷贝内层 dict） |
| N8 | `backend/app/api/agent.py` + `frontend/src/components/AICreation/AIChatPanel.tsx` | 后端：structured_results 抽取后（:1024 区域）收集 warnings → content 事件前 yield `{'type':'warning','message':'[G25a] 工序 5 …'}` SSE；前端：AIChatPanel 事件链加 `warning` 分支渲染 `⚠ message`（已核实现有 else-if 链对未知 type 静默忽略，向后兼容） |

### 轨道二：会话接续

| # | 文件 | 改什么 |
|---|------|--------|
| N3 | `backend/app/config.py` + `backend/app/services/project_state_service.py`（新）+ `tests/test_project_state_service.py` | 配置 `PROJECT_STATE_DIR`/`MEMORY_PROJECTS_DIR`（沿 MEMORY_DIR :120/:281 模式）；`ProjectStateService`：`load/update/update_from_turn/render_context_block`，`{project_id}.json` 滚动覆盖原子写（tmp+os.replace，拷 MemoryService :83 模式），schema 7 字段（current_task ≤200 字 / focus_chapters ≤5 / recent_intents ≤5 / user_preferences / last_session_id / updated_at / project_id），`render_context_block` 产 `## 项目当前工作状态` prompt 块（空 state 返回 ""） |
| N4 | `backend/app/services/memory_service.py` + `hierarchical_context.py` + `tests/test_memory_project_scope.py` | `get_project_memory_service(project_id)` 工厂（惰性建 `data/memory/projects/{project_id}/` 实例，dict 缓存）；`build_context`/`_load_filtered_memory` 加 `project_id` 可选 kwarg——项目目录优先、空则回退全局目录（现有 5 个全局文件不迁移不丢失） |
| N5 | `backend/app/api/agent.py` + `tests/app/api/test_agent_project_state.py` | `_build_orchestrator_context`（:1297）加载 state 渲染块（拷 :1366 profile_context 模式）+ `build_context` 传 project_id；`_build_llm_messages`（:1480）加 kwarg，system_parts 追加状态块（:1500 profile 之后）；新 `_update_project_state` 在三个 `_save_memory` 调用点（:1082/:1215/:1280）旁触发；`_save_memory` 加 project_id 路由到项目级 memory |
| N6 | `backend/app/agents/orchestrator/orchestrator.py` + `writing_agent.py` | `_dispatch_to_sub_agent`（:705）agent_task 加 `project_state_block`（源 `self._collected_info["context"]` :1828）；writing_agent `_do_template_fill` 读块，G25a/通用 system_msg 组装处追加一次（沿 `_get_preference_prompt_fragment` :1075 先例） |

### 收尾

| # | 文件 | 改什么 |
|---|------|--------|
| N9 | `ARCHITECTURE.md` + `DEV-LOG.md` | ARCHITECTURE 补：项目工作状态层（存储/注入点/schema）、按项目 memory 布局、LLM 韧性层、G25a warning 流（项目 CLAUDE.md 规则：架构改动收尾必须更新） |

## 依赖序

```
N1→N2→N7→N8→N9
N3→N4      N3→N5→N6→(合入 N8 前的 agent.py/writing_agent.py 顺序执行不交叉)
```
两条轨道并行推进，N5/N8 同碰 agent.py、N6/N7 同碰 writing_agent.py——顺序执行不交错。

## 禁区

- 不碰：登录/用户体系（同事线）、DB schema、前端大改（只 AIChatPanel 加 warning 分支）、模型配置/换模型
- 不动返回契约：`{"status","content","finish_reason","error"}` 4 键原样，全部增量加键（`error_class`/`warnings`/`project_state_block`）
- 不复活向量检索废弃组件；不迁移现有全局 memory 文件（回退兼容）
- 预存失败 `test_prompt_requires_step_name_prefix` 保持 deselect，不顺手修

## 验证

- 每节点单测（mock 模式 `monkeypatch.setattr(ls.llm_service, "generate_with_messages", AsyncMock(...))`，test_intent_recognizer.py:18 先例）
- 基线门（每节点后必跑）：`cd backend && python -m pytest tests -q --deselect tests/test_writing_agent.py::TestG25aContentPromptStepNamePrefix::test_prompt_requires_step_name_prefix` = **784 passed**（实测基线，非 DEV-LOG 旧数 718）0 新失败
- mock e2e 冒烟（无 vllm）：mock reachable + 脚本化响应（含一次 G25a 单行 error→恢复）→ POST generate-stream 带 project_id=1「继续改 G25a」→ 断言 state 文件落盘 focus_chapters 含 G25a、SSE 含 warning、二次调用 system message 含状态块
- 前端：`npm run build` TS 检查（PMF 冒烟级，视觉验证留部署环境）
- 留部署环境：真实 vllm 退避时序、真实 context overflow 裁剪效果、真实中文输入的 state 质量、warning UX

## 风险与缓解（已核实的）

- state 并发写：单 worker + threading.Lock + 原子替换（MemoryService 已验证模式）
- warning SSE 双向兼容：前端 else-if 忽略未知 type / 新前端不会从旧后端收到该 type
- 重试风暴：每行上限 3 次、退避 0.5/1.0s、Semaphore(4) 不变，最坏 +4.5s/失败行
- 裁剪破坏 JSON 指令：只裁 user 消息、只裁一次、system（指令所在）不动
