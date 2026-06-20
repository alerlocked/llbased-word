# PLAN: G25a 分工序并行生成

> seal commit 后不可变。Reviewer 从 git 读取。进度只记 DEV-LOG/git。
> slug: `g25a-perstep`（与 `ALIGN-g25a-perstep.md` 配对）

## Context（为什么做）

G25a 装配工艺卡片目前**单次 LLM 调用生成全部 10 道工序**的 content/inspection。两个问题：
1. **本地千问3-30B-A3B（mindie, maxIterTimes=2048）必截断**——单次 10 工序 content 远超 2048。这是用户切本地的刚需。
2. **即使云端 qwen-plus（8192），单次吐一大坨长输出，质量下降**（长输出易跑偏/重复），且工序越多越危险。

改法：**每道工序一次 LLM 调用，asyncio 并行（Semaphore 4）**。每工序专注生成自己 row 的 content/inspection，输出量 1/10，永不截断 + 质量高（专注单工序，力矩等参数准）。用户之前讨论的「10 工序分 10 个处理」方案。

模型：云端 qwen-plus 先验证架构（当前在用），本地千问3-30B-A3B endpoint/MODEL 配置留好，用户起 mindie 服务（port 1028）后改一行切本地。并发 4（用户定）。

## 改动清单

### 节点 A — is_g25a_sourced 分工序并行（核心）
| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/functional/writing_agent.py` | 注入点 `:920`（`if unstructured_cols:` 之前）：`is_g25a_sourced` 时分流，per-row unstructured（content/inspection，已在 unstructured_cols 里）改走新方法 `_generate_g25a_per_row_parallel`；非 G25a 走原单次逻辑（920-1097 不动）。新方法：遍历 n 工序，`asyncio.Semaphore(4)` + `asyncio.gather`（复用 orchestrator:2680 / pdf_queue_manager 模式），每工序构造 prompt（system_msg 基础 + 该工序 substeps 工步原文 + 画像 principles/triples + row=i 约束）→ `generate_with_messages(max_tokens≈2500)` → `_parse_llm_json` → slots(row=i)。合并所有工序 slots → `unstructured_slots`。单工序失败 log 不阻塞其他工序 |

复用：`llm_service.generate_with_messages`（已返回 finish_reason）、`_parse_llm_json`（:1865）、`merge_structured_with_unstructured`（structured_extractor:393）。per-row/chapter 区分：`unstructured_cols` 本来就只含 per-row（content/inspection），sub_sections 不在其中（chapter 级，G25a 当前生成不深度处理，保持现状）。

### 节点 B — 本地千问3-30B-A3B 配置留好
| 文件 | 改什么 |
|------|--------|
| `backend/.env`（或 config.py 注释） | 留好本地切换配置：`DASHSCOPE_BASE_URL_COMPLEX=http://localhost:1028/v1` + `MODEL_TIER_COMPLEX=qwen3-30b-a3b`。当前注释掉（用云端），用户起 mindie 服务后取消注释切本地。每工序 max_tokens 在本地场景下调到 ≤2048（mindie maxIterTimes） |

### 节点 C — 验证
- `diagnose_g25a.py`（无需改，内部透明）：content 10/10 + 看并行时间（vs 单次）+ 质量（力矩等参数准、不臆造）
- web 补齐验证（server 彻底重启加载新代码）
- `.test-runs/g25a-perstep/` 截图

## 禁区
- 不起 mindie 服务（用户做，port 1028）
- 不改非 G25a 章节生成逻辑
- 不改前端渲染（另案）
- 不碰 inject/extract 链路（g25a-write 已验证 OK）
- 不改 sub_sections（references/tech_notes/requirements）处理（chapter 级，保持现状）

## 验证（端到端）
1. `cd backend && conda run -n gywj --no-capture-output python diagnose_g25a.py` —— content 10/10 非空 + 并行（看 stdout 时间 vs 单次 ~30s）+ content 质量（力矩等参数）
2. **改核心代码后彻底重启后端**（gywj，别信 reload）：停 8000 → `conda run -n gywj python main.py`
3. 前端 :3000 补齐验证 G25a content（playwright localStorage 隔离测不了真实渲染，看后端日志 writing_task_completed + g25a 并行日志）
4. 每节点 `/checkpoint localknowledgebase-word`

## 进度锚
git commit = 每节点状态锚；DEV-LOG `## 当前状态` = 节点进度；PLAN seal 后不改内容。
