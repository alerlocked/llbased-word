# PLAN: 意图识别改 LLM + 修下游 dispatch 断链（多加测试）

> slug: `intent-llm-dispatch-fix`（总纲 `dialog-task-pipeline` 第四步）
> seal 后不可变。Reviewer 从 git 读本文件。

## Context（为什么）
对话任务分配链路断裂点 2:意图识别(intent_recognizer 关键词正则)→ task_decomposer → `_dispatch` 三套词汇表对不上,`document_generation`/`user_confirmation` 落 `unknown`(orchestrator.py:777),第三分支(非 draft_complete)对话任务跑空。单改识别白改(下游接不住),故本期:识别改 LLM + 修下游断链,让第三分支真通。

**范围(用户定 A)**:intent_recognizer 改 LLM(保留 11 类,fail-soft 关键词兜底) + `_dispatch` 补 `document_generation→writing` + `user_confirmation` noop + task_decomposer 核对。`detect_mode` 不动(保护 generate-stream 入口)。

## 改动清单

### `backend/app/agents/orchestrator/intent_recognizer.py`
| 改动 | 说明 |
|------|------|
| recognize() 加 LLM 分类 | `generate_with_messages(tier="simple", temp=0.1)`,prompt 照 `review_service._llm_check_entity_params` 范式 + JSON 容错解析(照 `_parse_missing_params`) |
| fail-soft 关键词兜底 | LLM 失败/超时/JSON 不可解析 → 退 `_match_intent_types` 正则;`_detect_draft_complete` 短路优先保留 |

### `backend/app/agents/orchestrator/orchestrator.py`
| 改动 | 说明 |
|------|------|
| `_dispatch` agent_mapping 补 | 加 `document_generation→writing` |
| `_dispatch` user_confirmation noop | `user_confirmation` → `{status:"skipped"}`(自动模式跳过) |
| shortcut 保护(硬约束) | process_intent :510 shortcut 不动 |

### `task_decomposer.py`
| 改动 | 说明 |
|------|------|
| INTENT_TO_TASKS 核对 | 确认 TaskType 都在 _dispatch 接得住;不动结构 |

### 测试(intent_recognizer 现 0%)
| 文件 | 测试 |
|------|------|
| `tests/test_intent_recognizer.py`(新) | LLM 分类各意图 / fail-soft 兜底 / JSON 容错 / draft_complete 优先 / @skip 真实 LLM |
| `tests/test_orchestrator_dispatch.py`(新/补) | document_generation→writing / user_confirmation noop / 现有 mapping 不破坏 |
| `test_orchestrator_interactive.py`(补) | shortcut 不走 LLM recognize |

## 禁区
- generate-stream/draft_complete/source-driven 主链:零改动。detect_mode 不动。意图集保留 11 类。

## 验证
1. pytest 新测试全过。2. 全量回归(~762,0 新 failed)。3. shortcut 保护(generation_mode→draft_complete 不调 recognize)。4. (可选)@skip 真实 LLM。

## 下游
验证通过 + commit,总纲 done 3/4(剩局部修改),统一经验回流。
