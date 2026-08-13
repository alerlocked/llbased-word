# 需求对齐卡：localkb 多人协作 git 治理 + 协作流程规范

## 目标
- 解决谁的什么问题：localkb 要进入多人协作，但仓库长期单人开发未推远程 → 远程 main 严重落后（自 2026-04 停滞）、分叉 380/1、工作区脏、无协作流程规范、架构层改动无隔离。
- 成功长什么样：① 远程 `main` 是可信基准，新协作者 clone 即最新 ② 有明文协作流程（分支/PR/review）③ 架构层（agents/检索/数据/生成主链）改动被隔离、强制 review，不混进功能 commit。

## 边界
- **做**：
  - force push 本地 main 对齐远程（打破 380 commit 推不上的死循环）
  - GitHub 配 `main` 分支保护（禁直推，走 PR）
  - 补 `.gitignore`（screenshots/deploy/e2e 报告/临时 data）+ 处理工作区 untracked
  - 写协作流程文档（CONTRIBUTING.md：分支模型 + PR 流程 + 架构层隔离清单 + commit 规范）
  - 更新项目 CLAUDE.md 过时段（"当前分支 feature/v1-cleanup" 已漂移到 main）
- **不做**：
  - 不重写本地历史（380 commit 全保留）
  - 不改保护区 hook 脚本（`scripts/devlog-hook.py` 的 best_effort_push 在协作下自适应：feature 分支 upstream = origin/feature-x，hook push feature 分支不碰 main；main 由保护规则兜底）
  - 不引入 CI / 测试覆盖率体系（PMF 阶段不做，除非用户明确要）

## 模糊点（全部已对齐 / 接受）
- 分叉方案 → **用户拍板 force push 覆盖远程**（已核实：远程唯一 commit `6056dc6` 的功能——material_index / reference_materials / FolderTree——本地 380 commit 已独立实现并超越，force push 不丢功能）
- 协作模式 → **main 保护 + feature 分支 + PR review**（用户拍板）
- 架构隔离 → **独立 PR + 强制 review**（用户拍板）
- 接受的不确定性：force push 丢弃远程 `6056dc6` 这个 commit（功能不丢）；远程 `feature/*`、`fix/ts-type-errors` 分支不受 force push 影响，但合回 main 时会冲突（协作者各自 rebase）

## 下游
- 治理动作直接执行（非业务代码 loop，按需回路）；协作规范落 `CONTRIBUTING.md`；架构层清单落文档 + 回写项目 CLAUDE.md。
