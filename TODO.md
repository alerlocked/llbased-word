# TODO · localknowledgebase-word

> 项目待办清单（债务 + 问题）。完成一条标 ✅ 或移到底部「已归档」。
> 来源：2026-07-19 gen-test-fixes 收尾梳理 + exp/DEV-LOG open items。
> 优先级：**挡交付 > 系统完善 > 治理小尾**。PMF 阶段服从商业（基本盘保交付，不过度工程）。

---

## P0 · 挡交付质量（优先）

### 1. G5a/G12a/G14a extract 漏抽（双层列头 colspan/rowspan）
- 现状：`structured_extraction_done` fields_found 低（G5a ref_name=1 / G12a quota=1 / G14a material_desc=0）。`documents/1` content.html table3/6/7 均为双层列头，`_extract_tabular_fields` 列映射偏移；G5a 首条"文件名称=小产品"系产品区串入
- 建议：**另立 lead**，逐章改 extract 列映射（对标 G25a 提质）。⚠ 区分 `g5a_file_refs_injected ref_count=5`（source-driven 注入正常）≠ `structured_extraction ref_name=1`（extract 债务）
- 关联：[[exp-generation-debugging]] 待办 / gen-test-fixes #1 归档

### 2. G4a 工艺文件目录 extract（同 #1 根因，更复杂）
- 现状：G4a 同 G5a 是文件目录类，但双层列（工艺文件名/编号 + 零部件代号/名称），未修，会同样串源/漏抽
- 建议：和 #1 **合并**到 extract 逐章提质 lead
- 关联：[[exp-fileref-source-extract]] 待办（G4a 独立设计，不能照搬 G5a）

### 3. G10a/G14a/G12a 前后端 column-key 不一致
- 现状：契约 guard 暴露 KNOWN_DIFFS（G10a `for_component_*`↔`for_*`、G14a `component_*`↔`comp_*`、G12a 前端多 `blank_yield`），guard 白名单兜底
- 建议：单独排期对齐（影响 structured 提取 + 前端取值 + 已有数据）
- 关联：[[exp-generation-debugging]] §1.7 / `scripts/hooks/guard-column-align.py` KNOWN_DIFFS

---

## P1 · 系统完善（场景驱动 / 上线前）

### 4. catalog enrich 同步 DB ~1s 残留阻塞
- 现状：`_enrich_names_from_catalog` 在 async 路径循环 33 次 sync `db.query().first()`，llm 改 async 后残留 1.05s 毛刺
- 建议：多端/上线准备期 offload（`asyncio.to_thread` 或 DB 改 async）。PMF 单用户可接受
- 关联：[[exp-async-llm-event-loop-blocking]] 待办 / gen-test-fixes #4 次要点

### 5. 本地千问3-30B-A3B per-step 实测
- 现状：分工序并行性能待实测（预期比云端 ~129s 快），需起本地服务（port 1028）
- 建议：麒麟部署链路通后测
- 关联：[[exp-generation-debugging]] §1.3/§4 待办

### 6. editorTemplateData 未持久化（前端）
- 现状：页面刷新后 AI 表格退化为 JSON 文本
- 建议：前端单独修
- 关联：[[exp-generation-debugging]] §3

### 7. G25a/documents 关联落库空（StepMaterial/StepTool）
- 现状：G25a colspan-heavy content 导致关联提取空
- 建议：低优先，等检索/知识图谱需求驱动
- 关联：DEV-LOG profile-expand-and-relations

---

## P2 · 治理 / 流程 / 小尾巴（不单独立项）

### 8. git 分叉债务（alerlocked/llbased-word）
- 现状：本地 main 与远程分叉，`1028785`/`bf954f2`/`b3143a2` 等 commit `best_effort_push` 全 skipped
- 建议：留项目 session 判断怎么对（push-only，不擅自 rebase/merge/force）
- 关联：memory `git-sync-unification-todo` / `python scripts/project-audit.py` 对账

### 9. diagnose 脚本被清
- 现状：`diagnose_all_chapters.py` / `diagnose_g25a.py`（exp 推荐诊断工具）已不在 backend/，本次 #1 靠 python -c + Read 临时顶
- 建议：要么恢复脚本进 `scripts/`，要么把诊断手法固化进 exp
- 关联：[[exp-generation-debugging]] §1.9/§2

### 10. profile 注入无日志
- 现状：`writing_agent.py:1012` 拼 `## 画像强约束` 进 system_msg 不打 logger，日志无法确认是否生效
- 建议：顺手加一行 log（做 #1 extract lead 时顺带）

### 11. VISION.md 未建
- 现状：项目无 VISION.md，gen-test-fixes 作为 bug 批次跳过了愿景校准
- 建议：下个新功能 lead 前补愿景 + 可观察验收（`/vision localknowledgebase-word`）
- 关联：lead 第 0 步强制校准

---

## 已归档 / 已完成
- 2026-07-19 gen-test-fixes：#2 /health 404、#3 SQL echo、#4 事件循环阻塞 67s —— 均已修（commit `bf954f2`）

---
*更新规则：完成一条 → 标 ✅ 或移「已归档」；新债务追加到对应优先级组。*
