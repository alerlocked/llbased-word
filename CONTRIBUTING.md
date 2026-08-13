# 协作开发规范

> 多人协作必读。仓库已 public，`main` 受 GitHub branch protection 保护。

## 1. 仓库状态

- 仓库 public：`github.com/alerlocked/llbased-word`
- `main` **受保护**：禁止直推、禁止 force push，所有改动走 **PR + 至少 1 个 review**
- 本地是 source of truth，远程跟随；分叉不擅自 pull/merge/rebase，暴露在 PR 里讨论

## 2. 分支模型

| 分支 | 用途 | 规则 |
|------|------|------|
| `main` | 稳定主干 | 只接 PR merge，禁直推 |
| `feature/<scope>-<desc>` | 功能 / 修复 | 从最新 `main` 切，完成后开 PR |
| `feature/arch-<desc>` | **架构层改动** | 独立分支，强制 review（见 §4） |
| `bugfix/<desc>` / `refactor/<desc>` | 修 bug / 重构 | 同 feature |

命名规范：`feature/csv-export-batch`、`bugfix/g18a-part-name`、`refactor/orchestrator-cleanup`。

## 3. 标准开发流程

```bash
# 1. 同步主干
git checkout main && git pull

# 2. 开分支（先确认本地 main 是最新）
git checkout -b feature/<your-feature>

# 3. 开发 + 提交（commit 规范见 §5）
git add <files>
git commit -m "feat(xxx): 一句话描述"

# 4. 推分支（post-commit hook 会自动 best-effort push 到 upstream）
git push -u origin feature/<your-feature>

# 5. GitHub 开 PR：
#    - base: main ← compare: feature/<your-feature>
#    - 涉及架构层 → 标题前缀 [architecture]（见 §4）
#    - 等 ≥1 个 review 通过

# 6. review 通过后 merge（squash 或 merge commit 均可），删远程分支
```

## 4. ⭐ 架构层改动隔离（强制 review）

**架构层**指以下文件 / 目录的改动（来源：`ARCHITECTURE.md`）：

| 架构层 | 文件 / 目录 |
|--------|------------|
| Agent 系统 | `backend/app/agents/**`（orchestrator / registry / state_machine / writing·review·proofread agent） |
| 上下文检索 | `backend/app/services/hierarchical_context.py`、`backend/app/services/knowledge_graph.py` |
| 数据存储 | `backend/app/models/database.py`（DB 表 / 字段） |
| 生成主链 | `backend/app/api/agent.py` 的 `generate-stream` 主链 |
| 架构文档 | `ARCHITECTURE.md` |

**规则**：

1. 架构层改动 → **独立分支** `feature/arch-*` + **独立 PR**，标题前缀 `[architecture]`，**强制 review**。
2. **功能 commit 不得混入架构层文件改动** → review 一律打回，拆成「功能 PR」+「架构 PR」分别提。
3. 架构层 PR merge 前，**必须同步更新 `ARCHITECTURE.md`**（项目 CLAUDE.md 规定：架构变更 lead 收尾更新单一架构源）。
4. 纯功能改动（前端组件、单个 agent 的 prompt 微调、新端点等）走普通 feature 分支即可，但 PR 描述里若意外触碰了上表文件，请主动说明。

> 判定标准：改了上表文件 = 架构层改动，无论改动大小。拿不准就当架构层处理（开 `[architecture]` PR）。

## 5. commit 规范

```
<type>(<scope>): <subject>
```

- **type**：`feat` / `fix` / `refactor` / `test` / `docs` / `chore`
- **scope**：模块名（如 `g25a`、`orchestrator`、`frontend`、`deploy`）
- **subject**：祈使句，简短描述

示例：`feat(g25a): per-row parallel generation + step numbering postprocess`

## 6. 新协作者入门

1. `git clone` → 先读三份文档：
   - `CLAUDE.md` —— 技术栈 / 怎么跑
   - `ARCHITECTURE.md` —— 当前架构（**唯一架构源**）
   - `DEV-LOG.md` —— 进度 / 历史决策（查「做到哪了」只认这个）
2. 后端：`cd backend && pip install -r requirements.txt && python main.py`（:8000）
3. 前端：`cd frontend && npm install && npm run dev`（:3000）
4. ⚠️ `.env` **不进 git**（`.gitignore` 已排除）。从 `backend/.env.example` 拷贝，填本地 LLM / VLM 地址（内网地址勿提交）。

## 7. 自动 hook 说明

- `.git/hooks/post-commit`（devlog-hook）每次 commit 自动刷新 `DEV-LOG.md` 的 git 段 + best-effort push 到当前分支 upstream。
- 在 feature 分支工作：upstream = `origin/feature/<x>`，hook 推 feature 分支，**不碰 main**（main 由 branch protection 兜底）。
- 所以 feature 分支上正常 commit 即可，hook 会帮你推分支；main 永远走 PR。

## 8. 禁区

- 不直推 `main`、不 force push `main`
- 不提交 `.env` / 密钥 / 内网真实 IP（脱敏用占位符 `SERVER_IP`）
- 不提交业务数据（`data/*.docx`、`backend/data/process_docs/`、`*.db` 等，`.gitignore` 已排除）
- 不擅自 pull/merge/rebase 解决分叉，分叉在 PR 里讨论
