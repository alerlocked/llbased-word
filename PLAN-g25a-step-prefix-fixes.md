# PLAN: G25a 三缺陷修复（工序名前置直拼 / 工序8引子合并 / G19a骨架噪声过滤）

> slug: `g25a-step-prefix-fixes` | ALIGN 已对齐（修法用户 2026-08-18 拍板，TODO 3c）
> 分支: `feature/arch-g25a-step-prefix-fixes`（架构层，单分支单 PR，标题前缀 `[architecture]`）

## 改动清单

| 节点 | 文件 | 改什么 |
|------|------|--------|
| N1 | `backend/app/services/hierarchical_context.py` + `backend/tests/test_hierarchical_context.py` | **缺陷②**：`extract_assembly_steps`（:1959 return 前）后处理——每工序 substeps 开头连续无 `^\d+\.\d+` 编号行（含折行断句）换行 join 并入首个带编号工步 content 头并丢弃独立步；首行已带编号（k==0）或全无编号（旧 step 9 案例，k>=len）不动。引子行非空 material/instruments 用 `、` 合并进首工步。**缺陷③**：`extract_process_steps` header_words（:1687）加「阶段标记/更改标记」+ append 前加 `re.match(r"^(?:共\s*\d+\s*页\|第\s*\d+\s*页)$", cell)` 过滤。新测试 class（复用 `_ctx_with` 合成 markdown 范式）：引子合并复现旧 bug 转绿 / 全无编号保持 / 首行带编号不动 / 噪声过滤复现（含 共2页、第 10 页 变体 + 含「第1页」字样长工序名不误杀） |
| N2 | `backend/app/agents/functional/writing_agent.py` + `backend/tests/test_writing_agent_g25a_resilience.py` | **缺陷①**：新增模块级 `_g25a_prefix_content(name, val)`——strip 行首 `{name}[：:]`（防 LLM 仍写导致重复，`^\s*{re.escape(name)}\s*[：:]\s*`）再前置 `f"{name}：\n"`；name/val 空不拼。接入两处：gen_one content slot（:1824-1828 编号 regex 后处理**之后**）、`_fallback_slots`（:1753 content 拼尾注后）。prompt 约束3（:1727）改：「不要写总起句——系统会在 content 头部自动前置「{name}：」，直接从 {i}.1 工步开始写操作」。前置守卫：grep 确认 `_generate_g25a_per_row_parallel` 仅 G25a 路径调用。新测试 class（复用 `_make_method` + mock llm_service 范式）：无前缀 content 得前缀（复现转绿）/ LLM 已写前缀不重复（全角半角冒号变体）/ 降级路径带前缀+尾注 / name 空不拼 / 现有测试兼容跑一遍 |
| N3 | 无新文件 | 全量回归门：`cd backend && python -m pytest -q` 守 853+新增 passed / 0 failed。真实 LLM 重生成冒烟**尽力探测**（后端+云端 LLM 可达则跑 documents/1 核对工序8 首列 8.1 真工步 + content 以工序名开头；不可行不阻塞，结论记 DEV-LOG，web 端验收留用户） |
| N4 | `ARCHITECTURE.md` + `TODO.md` + `DEV-LOG.md` | 架构层 PR 文档义务（CONTRIBUTING §4.3）：:38 extract 函数 bullet 补引子合并+页码过滤，:40 G25a per-row bullet 补「工序名程序化前置」；TODO.md 勾 3c；DEV-LOG 当前状态 + task_state |
| N5 | GitHub | push 分支（post-commit hook 自动）+ `gh pr create --title "[architecture] ..."` + `/pr-review localknowledgebase-word <pr号>` 多维审查 → 用户（admin）approve + merge |
| N6（2026-08-19 重 seal 增补，PR 审查 warn 用户拍板本 PR 内修） | `backend/app/services/document_profile_learner.py` + `backend/tests/test_document_profile_learner.py` | 物料 triple 提取改**全段提取**：材料格按 `、/,/，` 拆段，逐段走现有清洗管线（`len>=2` 守卫 + `^[^\s/]+` + spec_cut CJK 名 + `[:12]`）+ `_add`（seen-set 去重），不再 `split("、")[0]` 只取首段。用户原则：画像提取针对实际内容，不按行位置取首段（引子/材料限制生成用，旧文件不规范、生成要规范）。测试：一格多物料（酒精、白绸布、标记笔）→ 使用 triple 全产出；单物料不回归；空段跳过。完成后重跑全量 pytest + 更新 PR body |

## 禁区

- 不碰：`orchestrator.py` / `agent.py` generate-stream 主链 / 前端 / 模板 / `tests/fixtures/exports/` 垃圾清理（另项，不混架构 PR）
- 不做：6cbaf30 F2 状态块 A/B（3c 后生成效果仍差才查）/ 意图路由两病灶 + edit_local（TODO 3b）/ PR #63 复验（pr-watch 自动）
- 不直推 main 代码（branch protection；PLAN/ALIGN docs commit 先例除外）；PLAN seal 后不可变
- Lead 不直接 Edit/Write 业务代码——N1/N2 由 Writer subagent 执行

## 验证

- N1: `cd backend && python -m pytest tests/test_hierarchical_context.py -q`
- N2: `cd backend && python -m pytest tests/test_writing_agent_g25a_resilience.py tests/test_writing_agent.py -q`
- N3: `cd backend && python -m pytest -q`（全量 0 failed）
- N5: /pr-review 报告无 🔴 blocker → 用户 review merge
