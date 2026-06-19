# PLAN: G25a 装配工艺卡片「工序内容」撰写机制

> seal commit 后不可变。Reviewer 从 git 读取本文件做比对。进度只记 DEV-LOG/git，不碰本文件。
> slug: `g25a-write`（与 `ALIGN-g25a-write.md` 配对）

## Context（为什么做）

生成装配工艺规程时，G25a 装配工艺卡片的「工序内容(content)」当前为空，无法输出可用的工艺卡片。已诊断（`verify_g25a.py` 实测 + 代码静态分析）：

- **素材抽取健康**：material id=1 装配工艺卡片 `extract_assembly_steps` 正常返回 10 工序 / 52 工步（辅材/仪器齐全）。
- **断点在生成注入层**（静态逻辑必然，非偶发）：模板有 3 个 `generation_phases` → 必走 phased 模式。G25a 经 `template_required` 路径进 `missing_chapters` 但 `_doc_dir=""`（`orchestrator.py:1634`）；phased 注入点 B（`orchestrator.py:2620-2622`）取不到 doc_dir 且**无 fallback**，直接 `continue` → `assembly_steps` 不注入 → `writing_agent.is_g25a_sourced=False` → content 退化走普通 LLM 路径 → 空。
- **画像资源闲置**：`data/profiles/assembly.json` 的强约束（principles：章节完整性/数据可验证性/术语一致性）和参考值（triples：螺钉安装→1.9N·m 等力矩）是现成资源，但**只接入 review 任务，从未进写作 prompt**。

目标：①content 稳定生成非空 ②受画像两层约束（principles 强约束 + preferences 偏好）③力矩等参数工步原文优先、triples 兜底、绝不臆造 ④G22a 直填顺带验证落地。

## 改动清单

### 节点 A — 修 content 空（注入断点 fallback）
| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/orchestrator/orchestrator.py` | phased 注入点 B（G25a，约 :2611-2636）：doc_dir 取不到时，复用注入点 A（:2489-2508）的扫描 fallback——扫 `get_all_chapter_indexes()` 找含「装配」的章节取 `_doc_dir`，再 `extract_assembly_steps`。建议提公共方法 `_find_assembly_doc_dir()`，让注入点 A、B 共用，消除两处重复 |

复用：`hierarchical_context.get_all_chapter_indexes()` + `extract_assembly_steps()`（已验证健康，禁区不碰）。

### 节点 B — 接入画像两层 + triples 参考值
| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/orchestrator/orchestrator.py` | `_load_writing_preferences()`（:321-344）：`Profile.from_json` 之后，额外调 `writing_agent.load_profile(profile)`，把强约束(principles)+参考值(triples)传给写作 agent（现仅传 `WritingPreferences` 偏好层） |
| `backend/app/agents/functional/writing_agent.py` | ① 加 `self._profile` 字段 + `load_profile()` 方法（仿 `load_preferences` :1421）。② `is_g25a_sourced` 分支（:1010-1021）注入两块：**principles**（渲染 enabled 的 name+description，标「强约束必须遵守」）；**triples**（渲染 `s → r: o`，标「工步原文优先；原文缺失才参考下列值；两者都没有则留空，绝不臆造」） |

复用：`Profile.from_json()`（profile.py:437）。preferences/writing 偏好层已由 `_get_preference_prompt_fragment()`（writing_agent.py:1432，对所有章节生效）覆盖，**不重复注入**。

### 节点 C — web 端到端实测 + G22a 直填顺带验证 + 起点清理
| 文件 | 改什么 |
|------|--------|
| （验证为主，不改业务逻辑） | 前端 :3000 生成，截图 G25a content（非空 + 工步详情 + 力矩参考）+ G22a 直填（短词）。把 06-18 未提交改动（G22a 直填 / G25a 修复 / `extract_process_card_steps` 新增）与本次改动一起，按节点分 commit 清干净起点 |

## 禁区
- 不碰 `hierarchical_context.extract_assembly_steps`（抽取已健康）
- 不动 G19a skeleton 顺序（10 vs 12 步不一致，另案）
- 不引入外部标准文件（QJ903 等）—— 用户选「按画像来」
- 不重写 source-driven 生成架构，只补注入断点
- 不做测试体系/覆盖率（PMF 阶段，只冒烟）

## 验证（端到端）
1. `cd backend && conda run -n gywj --no-capture-output python verify_g25a.py` —— 抽取链路健康回归（应仍返回 10 工序/52 工步）
2. **改核心代码后彻底重启后端**（conda `gywj`，别信 reload——踩过假死坑）：停 8000 占用 → `conda run -n gywj --no-capture-output python main.py`
3. 前端 :3000（vite，端口以启动日志为准，曾见 3001）生成装配工艺规程，查 G25a content：
   - 后端 stdout 有 `g25a_assembly_steps_injected`，无 `g25a_no_doc_dir_fallback`
   - content 每道工序非空、含 1.1/1.2 工步详情
   - 力矩参数：工步原文有的抄原文；原文缺的有 triples 兜底值（如螺钉安装 1.9N·m）；两者都无则留空，无臆造
   - 术语一致（受 principles 约束）
4. 截图存 `.test-runs/g25a-write/`（gitignore，不进 git）；G22a 直填短词一并验证
5. 每节点 `/checkpoint localknowledgebase-word`（commit + DEV-LOG + wiki）

## 进度锚（执行 loop 依据）
- git commit = 每节点状态锚
- DEV-LOG `## 当前状态` = 节点进度
- PLAN seal 后不改内容，进度只记 DEV-LOG/git
