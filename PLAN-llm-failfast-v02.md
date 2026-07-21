# PLAN: LLM 不可达快速失败 + 画像/调试残留修复 + 同步打包 V0.2

> slug: `llm-failfast-v02` · 项目: localknowledgebase-word(主)→ win10
> 对齐卡: `ALIGN-llm-failfast-v02.md` · seal 后不可变

## Context(为什么改)

v0.2 部署机忘配内网 `.env` → LLM 回退公网默认地址 → 连不上。但系统**静默吞掉所有 LLM 连接错误、降级成空模板、最后返回 `success=True`**(假成功),把"模型没连上"这个根因藏了起来,只能拷日志逐行拼凑,调试成本巨大。

本次三件事一次做完:
1. **快速失败(核心)**:生成请求入口预探 LLM 可达性,不通 → 立即返回明确失败(整体失败不输出),不进生成流程。让这类问题以后一秒定位。
2. **顺带修两个通病 bug**:画像图谱 `graph.nodes` 是 dict 导致 slice 崩(回流麒麟已修的 `KnowledgeGraph` 方案)+ 删 `ntm-debug.txt` 调试残留。
3. **同步 win10 + 重打包 V0.2**:包内带 `.env.deploy.example` 模板,配合快速失败 = 下次忘配第一秒就喊出来。

> ⚠️ 不碰 orchestrator 状态机层静默(commit `8687cfd` 已修,不重复)。本次聚焦 **LLM 调用失败层**的静默。

## 关键现状(探索已确认)

- **入口已有"快速失败"范本**:`agent.py` `generate()` 第 880-888 行已有 `if not settings.DASHSCOPE_API_KEY: yield error + return`。新增的 LLM 预探照此模式插在 **888 行之后**(key 检查后、模式检测前)。
- **可复用探活逻辑**:`main.py:34` `_check_model_server()` 已用 `urllib.request` GET `{llm_url}/models`(timeout=5,URL = `DASHSCOPE_BASE_URL_COMPLEX or DASHSCOPE_BASE_URL`)。抽其 LLM 探活核心为复用函数。
- **SSE error 格式**:`{'type': 'error', 'error': '文本'}`(主流)。
- **回流零障碍**:主项目 `requirements.txt:53` 已含 `networkx>=3.0`;主项目标准 logging 就是 `from app.shared.logging import get_logger`,与麒麟 `knowledge_graph.py` 一致 → **直接复制,不改 import**。
- **async 阻塞坑**(`exp-async-llm-event-loop-blocking`):`generate()` 是 async,同步 `urllib` 探活会阻塞事件循环 → 必须 `await asyncio.to_thread(...)` 包;改 `llm_service` 后验证须**彻底重启后端**(uvicorn reload 假死),mock 验不了连接失败,要 HTTP 实测。

## 改动清单

### 节点 1 · 快速失败核心(主项目)— 1 commit

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/llm_service.py` | 新增 `check_llm_reachable() -> tuple[bool, str]`(同步 urllib GET `/models`,timeout=5,URL=`DASHSCOPE_BASE_URL_COMPLEX or DASHSCOPE_BASE_URL`,带 Bearer key 头)。返回 `(True, "")` 或 `(False, reason)`。逻辑照搬 `main.py:46-51`。 |
| `backend/app/api/agent.py` | ① `generate()` 888 行后插预探:`reachable, reason = await asyncio.to_thread(llm_service.check_llm_reachable)`;不通 → `yield {'type':'error','error':f'模型服务不可达:{reason}。请检查 .env 内网地址(DASHSCOPE_BASE_URL_COMPLEX)及模型服务状态。'}` + `return`。② **删 1009-1019 行 `ntm-debug.txt` 调试残留**(Bug3)。 |

**验证**:改 `.env` 把 LLM 地址指向不通地址 → 重启后端 → POST `/api/agent/generate-stream` → 收到 `type:error`(非 `success=True` 空内容)。改回内网地址 → 正常生成(回归)。

### 节点 2 · 画像图谱回流(主项目)— 1 commit

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/knowledge_graph.py` | **新增**(从麒麟 `llbased-word-kylin/backend/app/services/knowledge_graph.py` 整文件复制,393 行。import 已兼容,不改) |
| `backend/app/models/profile.py` | `to_context_text` 第 400-409 行(老:直接 `nodes[:20]` 切片)替换为麒麟版:`kg = KnowledgeGraph.from_dict(self.graph); graph_text = kg.to_context_text(max_tokens=300); if graph_text: parts.append("知识关系图:\n" + graph_text)` |

**验证**:加载 `data/profiles/assembly.json` 不再报 `unhashable type: 'slice'`;`to_context_text()` 产出含图谱关系;pytest 回归。

### 节点 3 · 同步到 win10 — 1 commit

把节点 1、2 的改动同步到 `localknowledgebase-word-win10/backend/app/`:
- `api/agent.py`(快速失败预探 + 删 ntm-debug,win10 行号同构 1009-1019)
- `services/llm_service.py`(`check_llm_reachable`)
- `services/knowledge_graph.py`(新增)
- `models/profile.py`(to_context_text 图谱段)

> win10 `main.py` 已有 `_check_model_server`(34-79),不用动。sync 单向覆盖 `app/`,改上游主项目再 sync(`exp-kylin-deploy-shared-bugs`)。

**验证**:win10 backend `python -c "from app.api.agent import router"` import OK;起后端冒烟。

### 节点 4 · 打包 V0.2(win10)— 1 commit

- 按 `localknowledgebase-word-win10/DEPLOY.md` 流程重新打包(`conda pack -n gywj` → 解压 `dist/工艺文件系统/env/` → 同步 `app/` + `frontend/dist` → 配 `.env`)。
- **包内确保带 `.env.deploy.example`**(内网 153 模板)。配合节点 1 快速失败 + 启动 `_check_model_server` WARNING = 忘配时强提示。
- **版本号统一**:`backend/app/config.py` `VERSION: str = "0.1.0"` → `"0.2.0"`(启动.bat 已硬编码 v0.2,顺手对齐)。
- 产出 `dist/工艺文件系统/` + `gywj_v0.2.zip`。

**验证**:dist 启动(`启动.bat`)→ banner 显示 v0.2 → 不配 `.env` 触发生成 → 收到"模型服务不可达"明确报错(端到端坐实快速失败)。

## 禁区

- ❌ orchestrator 状态机层静默(`8687cfd` 已修)
- ❌ `.env` 配置本身(内网地址现场配,本次只带模板)
- ❌ 前端 UI(后端 SSE `error` 为准)
- ❌ 运行中熔断(本次只入口预探)
- ❌ VLM/PDF 解析链路

## 验证(端到端)

1. **快速失败(核心验收)**:后端**彻底重启**(taskkill,非 reload)→ `.env` LLM 指不通地址 → generate → SSE `type:error` 文案含"模型服务不可达";改回内网 → 正常生成。
2. **画像**:`assembly.json` 加载日志无 `unhashable type: 'slice'`。
3. **Bug3**:运行无 `[Errno 2] D:\tmp\ntm-debug.txt`。
4. **回归**:主项目 pytest(基线 676 passed)0 新 fail。
5. **打包**:win10 dist 启动 v0.2 + 忘配 `.env` 时 generate 明确报错。

## 执行注意

- 复杂节点用 Writer subagent;Reviewer 读 git 中 seal 的 PLAN 比对 diff ⊂ 改动清单且 ∩ 禁区 = ∅。
- 每节点 checkpoint commit + DEV-LOG 状态;收尾三件套(清临时文件 / task_state:done / 经验回流 wiki)。
- 改 `llm_service` 验证必须彻底重启后端。
