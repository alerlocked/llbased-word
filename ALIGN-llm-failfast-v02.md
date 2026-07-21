# 需求对齐卡:LLM 不可达快速失败 + 画像/调试残留修复 + 同步打包 V0.2

> slug: `llm-failfast-v02` · 项目: localknowledgebase-word · 2026-07-21

## 背景
v0.2 部署机忘配内网 `.env` → LLM 走公网默认地址 → 连不上 → 系统静默吞掉所有 LLM 失败、降级空模板、照常返回 `success=True`(假成功)。调试成本巨大(拷日志拼凑)。根因见本会话根因分析。

## 目标
- **解决谁的什么问题**:v0.2(及主/win10 同源)在 LLM 不可达时静默假成功,把"模型没连上"这个根因藏起来,排查极难。
- **成功长什么样(可观察)**:
  1. 把 `.env` 指向不通的地址 → 触发生成 → SSE 收到明确 `error` 事件(文案含"模型服务不可达/请检查配置"),**而非** `success=True` + 空内容
  2. 画像加载日志不再出现 `unhashable type: 'slice'`
  3. `agent.py` 运行无 `[Errno 2] D:\tmp\ntm-debug.txt`
  4. 主项目 + win10 改动一致;win10 重新打包出 V0.2,包内带 `.env.deploy.example`,启动检测 `.env` 缺失/LLM 不通时强提示

## 边界
**做**:
- 主项目 backend/app:`generate` 入口(`agent.py` `generate_stream`)预探 LLM 可达性,不通 → 整体失败,发明确 SSE `error`
- Bug2:回流麒麟 `services/knowledge_graph.py` + 改 `models/profile.py` `to_context_text` 用 KnowledgeGraph(根治 `graph.nodes` dict)
- Bug3:删 `agent.py` `ntm-debug` 调试残留(主 + win10 + 麒麟三端)
- 同步主 → win10(本次改动的 app/ 文件)
- win10 重新打包 V0.2 + 包内带 `.env` 模板 + 启动强提示

**不做**:
- 不碰 orchestrator 状态机层静默(commit `8687cfd` 已修,不重复)
- 不改 `.env` 配置本身(内网地址现场配,本次只带模板 + 提示)
- 不做运行中熔断(本次只入口预探)
- 不改前端 UI(后端 SSE `error` 事件为准;前端现有 error 展示能消费。若展示不足再议)
- 不碰 VLM/PDF 解析链路

## 模糊点(已清零)
1. 失败反馈形式 → **整体失败不输出**(已定)
2. 探活策略 → **入口预探**(已定)
3. Bug2 范围 → **纳入,回流 KnowledgeGraph**(已定)
4. 打包 `.env` → **带模板 + 强提示**(已定)
5. 状态机层 → 不动(`8687cfd` 已修,已澄清)
6. 前端 → 不改(SSE error 为准,已澄清)

## 关键约束(给 Writer,摘自 pitfalls / exp)
- `exp-kylin-deploy-shared-bugs`:sync 单向覆盖 `app/`,业务 bug 改上游主项目再 sync
- `exp-async-llm-event-loop-blocking`:`llm_service` 已 `AsyncOpenAI`,改后必须彻底重启后端(reload 假死);mock 验不了连接失败,要 HTTP 端到端实测
- pitfalls T02:禁 `Path(__file__).parent.parent / ...`
- pitfalls:commit 前查 `git diff --cached` 无敏感数据(`.env`/db)
- 画像 `graph.nodes` 是 dict(`assembly.json` 实证),麒麟 `KnowledgeGraph.from_dict` 正确吃 dict

## 下游
- → 进 PLAN(slug: `llm-failfast-v02`)
