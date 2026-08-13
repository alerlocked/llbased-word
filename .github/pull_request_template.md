## 改动概述
<!-- 一句话说清改了什么、为什么 -->

## 改动类型
- [ ] 功能（feature）
- [ ] 修复（bugfix）
- [ ] 重构（refactor）
- [ ] 文档（docs）
- [ ] **架构层**（见 [CONTRIBUTING](../CONTRIBUTING.md) §4）→ PR 标题加 `[architecture]` 前缀

## ⭐ 架构层自查（必填）
是否触碰以下文件？（任一勾选 = 架构层改动，CODEOWNERS 强制 admin review，且 `ARCHITECTURE.md` 必须同步更新）
- [ ] `backend/app/agents/**`（orchestrator / registry / state_machine / 各 agent）
- [ ] `backend/app/services/hierarchical_context.py` / `knowledge_graph.py`
- [ ] `backend/app/models/database.py`（DB 表 / 字段）
- [ ] `backend/app/api/agent.py` 的 generate-stream 主链
- [ ] `ARCHITECTURE.md`

> 拿不准是否算架构层 → 当架构层处理（勾选 + 加 `[architecture]` 前缀）。

## 自测
- [ ] 后端 `pytest` 通过（或说明未跑原因）
- [ ] 前端 `tsc` 0 错
- [ ] 冒烟：核心流程（生成 / 审校 / QA）跑通

## 备注
<!-- breaking change / 待办 / 需部署环境验证的留这里 -->
