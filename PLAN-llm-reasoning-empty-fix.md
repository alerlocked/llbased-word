# PLAN: 阶段1 — LLM 非流式推理模型空 content 修复（Gap C 止血）

> slug: `llm-reasoning-empty-fix`（阶段1，seal 后不可变）
> 上游对齐卡：`ALIGN-g25a-method-aux-bind.md`（阶段2 相辅相成新模型，本轮不做）
> 范围决策（用户定）：分阶段——本轮只止血 Gap C；相辅相成新模型留阶段2。

## Context（为什么改）

2026-07-23 内网部署（F 盘 gywj-0.3，模型 qwen3-30b-a3b）补齐工作流出三问题，定位后**问题1（"llm 读取失败"）+ 问题3（装配工艺卡片工序内容全空）同根**：

- **根因**：`llm_service.py:generate_with_messages`（非流式）用 `extra_body={"enable_thinking": False}`（`:414`），与 qwen3-30b-a3b 推理模型冲突 → `message.content` 系统性返回空串；且只读 `content`（`:417`），忽略 `reasoning_content`；**content 空时仍返回 `status:success`（静默假成功）**。
- **下游表现**：
  - `_detect_missing_chapters`（`orchestrator.py:1985`）`json.loads("")` → "Expecting value: line 1 column 1 (char 0)"（日志 14:57、16:30 两次）= 用户看到的"llm 读取失败"。
  - G25a 装配卡 10 道工序 LLM 生成全失败（`g25a_per_step_parallel_done slots=0`）→ 工序内容（工艺方法）列 10 行全空。
- **流式正常**：`generate_with_messages_stream`（`:444`）用 `enable_thinking=True`（`:468`）+ 正确读 `reasoning_content`（`:479`），qa 流式 22 秒正常输出。证明模型服务没坏，纯粹是非流式 + 推理模型适配 bug。
- **本地不暴露**：本地 GLM-5 非推理模型，content 正常；部署到 qwen3 才炸（同 `exp-silent-fake-success-fast-fail` 病根的变种）。

**预期结果**：非流式 LLM 调用在 qwen3 推理模型上能拿到非空 content；content 空不再静默 success，而是降级流式收集、仍空则显式报错。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/llm_service.py` → `generate_with_messages`（381-442） | ① `extra_body` `enable_thinking: False → True`（对齐流式，让推理模型正常输出 content）；② **只读 `message.content`，不合并 `reasoning_content`**（思考过程非最终答案，合并会污染 JSON 场景）；`reasoning_content` 可 `logger.debug` 供调试，不进返回；③ **content 空（strip 后）兜底**：降级流式收集重试一次 → 仍空则 `status:error`（fail-fast，不再静默 success）。返回结构 `{status, content, finish_reason}` 不变（对 17 处调用方透明）。 |
| `backend/app/services/llm_service.py` → 新增 `_collect_stream_content`（私有辅助） | 内部流式收集完整 content 字符串：复用 `enable_thinking=True` + 只取 `delta.content`（丢弃 `delta.reasoning_content`），返回 `(content, finish_reason)`。供上面③降级用。 |

## 禁区

- 不碰 `generate_with_messages_stream`（流式已正常）。
- 不碰 `deepseek_service.py`（独立客户端；本次范围外）。
- 不改 17 处非流式调用方——返回结构不变，对它们透明。
- 不动章节生成/检索逻辑（阶段2 范围）。
- 不新增配置项、不建新库。
- 不在 F 盘部署版直接 hotfix（主仓改 + 重新打包，打包时机另决）。

## 验证

1. **冒烟（核心）**：主仓起后端，触发 G25a 补齐生成 → 日志 `g25a_per_step_parallel_done slots>0`，装配卡工序内容（工艺方法）列非空。
2. `_detect_missing_chapters` 不再报 "Expecting value: line 1 column 1 (char 0)"。
3. **降级路径**：日志确认 `enable_thinking=True` 后 content 直接非空（降级流式 ideally 不触发）；若触发降级，确认降级流式能拿到 content。
4. **回归**：qa 流式路径未改，不受影响；其他非流式调用方正常。`pytest` 回归（基线 676 passed，0 新 failed）。
5. ⚠️ **已知留观察**：`enable_thinking=True` 增加单次调用延迟（thinking）；"好久没反应"（90 分钟）的彻底优化（并行/超时调优）不在本阶段，修完观察是否缓解。
