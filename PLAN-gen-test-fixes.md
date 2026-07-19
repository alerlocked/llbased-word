# PLAN: 完整生成测试暴露的后端问题处理

> seal 2026-07-19。slug=`gen-test-fixes`。对齐卡 `ALIGN-gen-test-fixes.md`。
> 诊断详见 `C:\Users\alerl\.claude\plans\scalable-inventing-llama.md`（含 Explore agent 笔误修正）。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `backend/main.py` | `app.mount("/", StaticFiles(frontend/dist))` 块（301-306）移到 `@app.get("/health")`(318) **之后**注册（文件末尾），让 API 路由 + health 先于 SPA fallback 匹配 |
| `backend/app/config.py` | Settings 加 `SQL_ECHO: bool = False`（`DEBUG:16` 附近） |
| `backend/app/database.py` | `:15` `echo=settings.DEBUG` → `echo=settings.SQL_ECHO`（解耦 SQL echo 与 DEBUG/reload） |
| `backend/app/services/llm_service.py` | `:8` `OpenAI`→`AsyncOpenAI`；`:31/:37` 两 client `OpenAI(...)`→`AsyncOpenAI(...)`；所有 `.chat.completions.create(` 加 `await`（方法已 async def，调用链不动）。照搬 `deepseek_service.py:36-39/76` |
| （节点 1，不改代码） | 跑 `diagnose_all_chapters.py` 实证 G5a/G12a/G14a extract 源 vs 抽到 → 结论进 DEV-LOG + exp（已知 extract 债务，逐章提质另立 lead） |

## 禁区
- 不改前端 `frontend/`
- 不改 extract/colspan/表头映射（#1 只诊断归档，修复独立 lead）
- 不动生成业务逻辑（模板 / derive / review / writing_agent 生成 prompt）
- 不碰南天门核心区（`~/.claude/`、根 CLAUDE.md/.env/scripts/memory）

## 验证
- `cd backend && conda run -n gywj python -m pytest`（基线 673 passed 不回归，draft flaky 预存忽略）
- 改完彻底重启后端（exp §3 reload 假死）→ `curl http://127.0.0.1:8000/health` 秒回 200 + 日志无 `sqlalchemy.engine.Engine` INFO
- 重跑完整生成 documents/1：11 章 `writing_task_completed`，并发 `curl /health` 不再卡 67s，生成结果不变
