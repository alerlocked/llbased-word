# PLAN: G25a 装配工艺卡片「工序内容」撰写机制（v2 根因修正）

> seal commit 后不可变。Reviewer 从 git 读取。进度只记 DEV-LOG/git。
> v1 假设「注入断点」经诊断推翻（fill 模式注入层 OK），根因改定位 LLM 生成层。
> slug: `g25a-write`（与 `ALIGN-g25a-write.md` 配对）

## Context（为什么做）

G25a 装配工艺卡片的「工序内容(content)」在**补齐(fill)模式**下为空。诊断（2026-06-19，纯代码可证）：

- **注入层 OK**：fill 模式走 `_detect_missing_chapters`，上传文件已解析有 chapter index，`_doc_dir` 有值；注入点 A（orchestrator:2489，注释 BOTH 模式 + 有 fallback）+ `verify_g25a.py` 实证 + memory 06-18 运行时 is_g25a_sourced=True → **注入成功**。
- **merge 层 OK**：`_legacy_to_slots`（writing_agent:1859）/ `merge_structured_with_unstructured`（structured_extractor:393）都正确填 content——LLM 返回了就绝不丢。
- **根因 = LLM 生成层 max_tokens 截断**：G25a 是 10 工序 × (content/inspection/references/tech_notes/requirements) 全是 long_text，单次输出撞 `max_tokens=6000` → 截断 → `_parse_llm_json`（writing_agent:1809）返回 None → `unstructured_slots` 空 → content 空。**sparse retry（1205）只在 item_count==0 触发，但 G25a 直填了 structured 列（step_no/step_name 有行），item_count>0 → 不 retry → 永远空**。
- `generate_with_messages`（llm_service:394）只返回 content，**不返回 finish_reason**，writing_agent 无从知道截断。
- 画像资源闲置：principles/triples 未接入写作 prompt。

目标：①content 稳定非空 ②受画像两层约束（principles 强约束 + preferences 偏好）③力矩等参数工步原文优先、triples 兜底、绝不臆造 ④G22a 直填验证落地。

## 改动清单

### 节点 A — 修 LLM 层截断（content 空根因）
| 文件 | 改什么 |
|------|--------|
| `backend/app/services/llm_service.py` | `generate_with_messages`（:358）返回值加 `finish_reason`（response.choices[0].finish_reason），让调用方能检测截断 |
| `backend/app/agents/functional/writing_agent.py` | ① G25a/process_card 的 `max_tokens` 6000 → 8192（qwen-plus 安全上限）。② LLM 返回后检测 `finish_reason=="length"`（截断）→ log warning `g25a_content_truncated` + 用更大 max_tokens retry 一次。③ 若 retry 仍截断 → 纠错升级分批生成（见下） |

验证：web fill 模式补齐，G25a content 非空、含工步详情。stdout 无 `g25a_content_truncated`（或有但 retry 后 content 出来）。
**若提 max_tokens 仍空（content 真超 8192）→ 节点 A.2：is_g25a_sourced 按工序分批调 LLM（每批 3 工序，max_tokens 充足），合并 slots。**

### 节点 B — 接入画像两层 + triples 参考值
| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/orchestrator/orchestrator.py` | `_load_writing_preferences()`（:321-344）：`Profile.from_json` 后额外调 `writing_agent.load_profile(profile)`，把 principles(triples) 传给写作 agent |
| `backend/app/agents/functional/writing_agent.py` | ① 加 `self._profile` + `load_profile()`（仿 load_preferences :1421）。② `is_g25a_sourced` 分支（:1010-1021）注入：principles（enabled 的 name+description，标强约束）+ triples（s→r:o，标「工步原文优先；原文缺才参考下列值；两者都无留空，绝不臆造」） |

复用：`Profile.from_json()`（profile.py:437）。preferences/writing 偏好层已由 `_get_preference_prompt_fragment()`（:1432）覆盖，不重复注入。

### 节点 C — web 端到端实测 + G22a 直填验证 + 起点清理
| 文件 | 改什么 |
|------|--------|
| （验证为主） | 前端 :3000 **补齐模式**生成（复用 `_test_g25a.py` 或前端手动），截图 G25a content（非空+工步详情+力矩参考）+ G22a 直填（短词）。06-18 未提交改动 + 本次改动按节点分 commit 清起点 |

## 禁区
- **不动注入层**（orchestrator 注入点 A/B，已验证 OK）——v1 在这白假设过
- 不动 `hierarchical_context.extract_assembly_steps`（抽取健康）
- 不动 G19a skeleton 顺序（10 vs 12 步，另案）
- 不引入外部标准文件（QJ903 等）—— 按画像来
- 不重写 source-driven 生成架构
- 不做测试体系/覆盖率（PMF 阶段）

## 验证（端到端）
1. `cd backend && conda run -n gywj --no-capture-output python verify_g25a.py` —— 抽取链路回归
2. **改核心代码后彻底重启后端**（gywj，别信 reload——踩过假死坑）：停 8000 → `conda run -n gywj --no-capture-output python main.py`
3. 前端 :3000 补齐模式生成，查 G25a content：每工序非空 + 工步详情；力矩参数工步原文优先/triples 兜底；术语一致
4. 截图存 `.test-runs/g25a-write/`（gitignore）；G22a 直填一并验证
5. 每节点 `/checkpoint localknowledgebase-word`

## 进度锚
git commit = 每节点状态锚；DEV-LOG `## 当前状态` = 节点进度；PLAN seal 后不改内容。
