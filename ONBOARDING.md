# 协作开发上手（给新同事）

> 5 分钟看完，照着干。完整规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 这个项目是干嘛的

工艺文件辅助编辑系统：**工艺意图 → 标准工艺术语 → 工艺文件生成**。多层 Agent + 表格生成。
技术栈：React 18 + TS + Vite（前端）/ Python 3.13 + FastAPI（后端）/ LangChain + GLM（AI）。
架构看 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 第一次：环境准备

```bash
git clone git@github.com:alerlocked/llbased-word.git   # 或 fork 后 clone 自己的
cd llbased-word

# 后端
cd backend && pip install -r requirements.txt && python main.py   # http://127.0.0.1:8000

# 前端（另开终端）
cd frontend && npm install && npm run dev                          # http://127.0.0.1:3000
```

- `.env` **不进 git**：从 `backend/.env.example` 拷贝一份，填本地 LLM/VLM 地址（找 @alerlocked 要配置）。
- 先读三份：[CLAUDE.md](CLAUDE.md)（技术栈/怎么跑）、[ARCHITECTURE.md](ARCHITECTURE.md)（架构）、[DEV-LOG.md](DEV-LOG.md)（进度/历史决策）。

## 日常开发：5 步循环

```bash
# 1. 从最新 main 切分支
git checkout main && git pull
git checkout -b feature/<你的功能>        # 命名：feature/ | bugfix/ | refactor/

# 2. 开发 + 提交（commit 规范见下）
git add <files>
git commit -m "feat(xxx): 一句话描述"

# 3. 推分支（post-commit hook 会自动帮你推）
git push -u origin feature/<你的功能>

# 4. GitHub 开 PR：base=main ← 你的分支，填模板（改动概述 + 架构层自查 + 自测）
# 5. 等 @alerlocked 审 → 按 review 改 → merge
```

**commit 规范**：`<type>(<scope>): <subject>`
- type：`feat` / `fix` / `refactor` / `test` / `docs` / `chore`
- 例：`feat(g25a): per-row parallel generation`、`fix(frontend): table column align`

## 关键规矩（必看）

| ✅ 要做 | ❌ 不要做 |
|--------|----------|
| 一个功能一个 commit，消息清晰 | 直推 `main`（受保护，必须走 PR） |
| PR 模板认真填（尤其**是否动架构层**） | 碰**架构层**文件（见下），除非单独开 `[architecture]` PR |
| 不确定能不能改 → PR 里问 | 提交 `.env` / 密钥 / 内网地址 / 业务数据（`.docx` 等） |

**架构层文件**（改动需独立 `[architecture]` PR + 强制 admin 审，CONTRIBUTING §4）：
- `backend/app/agents/**`
- `backend/app/services/hierarchical_context.py`、`knowledge_graph.py`
- `backend/app/models/database.py`
- `backend/app/api/agent.py` 的 generate-stream 主链
- `ARCHITECTURE.md`

> 拿不准是否算架构层 → 当架构层处理（开 `[architecture]` PR）。

## 审查流程

PR 提交后：**南天门（AI）审 diff**（bug / 架构越界 / 品味）+ **@alerlocked 把关** → 通过则 merge。架构层 PR 强制 admin 审。一般 1-2 轮 review。

## 卡住了怎么办

- 环境/配置问题 → 找 @alerlocked 要 `.env` 配置
- 不确定改动是否越界（碰了架构层？）→ PR 里直接 @alerlocked 问
- 完整规范（分支模型 / commit / 禁区 / hook 说明）→ [CONTRIBUTING.md](CONTRIBUTING.md)
