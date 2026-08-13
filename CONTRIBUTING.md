# 协作开发规范

> 多人协作必读。仓库已 public，`main` 受 GitHub branch protection 保护。

## 1. 仓库状态

- 仓库 public：`github.com/alerlocked/llbased-word`
- `main` **受保护**：禁止直推、禁止 force push，所有改动走 **PR + 至少 1 个 review**
- **PR 审查路由**：`CODEOWNERS` 强制所有 PR 必须经 `@alerlocked`（admin）review 才能 merge；协作者互相 approve **不算数**。架构层（§4）同样强制 admin review。
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
#    - 等 admin(@alerlocked) review 通过 —— CODEOWNERS 强制,
#      协作者互相 approve 不算数

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
>
> `/pr-review` 会**自动检测 §4 越界**（功能 PR 混入架构层文件 / 架构层 PR 未更新 `ARCHITECTURE.md` / 架构层未走独立 `[architecture]` 分支）→ 直接判 🔴 blocker。靠机器兜底，不纯靠人眼。

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

## 9. PR 审查流程

1. **开 PR**：填 PR 模板（`.github/pull_request_template.md`），声明改动类型 + **是否触碰架构层** + 自测结果。
2. **南天门多维审查**：admin 在本地 NTM session 跑 `/pr-review localknowledgebase-word <pr号>`（无 PR 号则审当前分支）。它**复用 Claude Code 底座**（`/code-review` 查 bug/简化 + `/security-review` 查安全）+ **补三处南天门增量**：
   - **架构层越界**（§4 清单 diff 比对 + 是否同步更新 `ARCHITECTURE.md`）
   - **项目经验**（wiki 经验库 `exp-*.md` + `pitfalls.md` 踩坑匹配）
   - **品味**（`guard-taste` 规则）

   输出**分级报告**：🔴 blocker（必修）/ 🟡 warn（应修）/ ⚪ nit（可选），每条引来源（§4 规则号 / exp 文件 / taste T0x / CC 输出）。
3. **admin 把关**：`@alerlocked` 看报告 + 自查 → **approve**（架构层 PR CODEOWNERS 强制 admin approve；blocker 必修后才能 merge，warn 评估）。
4. **merge**：review 通过后 merge，删分支。

> 南天门多维审查（`/pr-review`）已于 2026-08-14 落地：通用 bug/安全走 CC 底座不重造，南天门只补 CC 不知道的「架构层边界 / 项目经验 / 品味」三处增量。命令在 NTM 核心层 `.claude/commands/pr-review.md`，**项目无关**——审查时自动读本项目的 §4 清单 / 经验 / pitfalls。
