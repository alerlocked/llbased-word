# PLAN: 生成质量回归修复（slug: `gen-quality-fix`）

> 项目: localknowledgebase-word | seal: 2026-07-09 | 承接 `ALIGN-gen-quality-fix.md`
> seal 后不可变，进度记 DEV-LOG/git。

## Context

2026-07-09 端到端生成暴露 4 个质量回归（feedback-rules 落地后首测）。pytest 全量 0 failed（674 passed），但**实际生成内容不可用**：6 个列表章节全空、G22a 工艺过程卡工序名丢失（退化给 LLM）、助手话术自相矛盾、记忆服务报错。4 个根因已通过日志铁证 + 代码静态分析全部定位。本 PLAN 修复这 4 个回归，恢复生成可用性。

## 改动清单

### 节点1 — derive 强节点 import 缺失（空章节根因）★最痛
- **根因**：`writing_agent.py:1450` `derive_list_strong()` 运行时调 `TemplateColumn.from_dict()` 但方法内**无局部 import**（commit `105f248` 引入时漏，pytest 未覆盖该路径）→ NameError → `orchestrator.py:936` catch → G4a/G5a/G10a/G12a/G14a/G18a **6 章节派生跳过 → 空表**。
- **改**：`derive_list_strong` 方法开头补 `from app.services.template_types import TemplateColumn`（参照同文件 :768 `_do_template_fill` 模式）。1 行。

### 节点2 — G22a process_card_steps 注入 fallback（过程卡退化根因）
- **根因**：`orchestrator.py:2780-2803` G22a 注入依赖 `_collected_info["missing_chapters"]` 中 `mc.title == task.chapter_title` 条目的 `_doc_dir`；日志铁证 `g22a_no_doc_dir_fallback`（doc_dir 取空）→ 注入跳过 → `writing_agent.py:890 if chapter_code=="G22a" and _card_steps:` 假 → step_desc 交 LLM（退化）。`doc._doc_dir` 填充正常（`_build_doc_dict:260`），断点缩到 **title 精确匹配 / `_collected_info` 存储**。
- **改**：执行首步加临时日志 diagnose（打印 `task.chapter_title` + `_collected_info["missing_chapters"]` 各条 title/_doc_dir）→ 定位确切断点 → 修（候选：title 匹配放宽互含 / 修 `_collected_info` 存入 / doc_dir 兜底）→ 验证 `g22a_process_card_steps_injected` 出现 + step_desc 直填工序名。
- 复用：`extract_process_card_steps`（hierarchical_context.py:1703）+ G22a 直填段（writing_agent.py:888-905）已存在，注入成功即生效。

### 节点3 — 话术矛盾（素材库 vs 知识库）
- **根因**：`agent.py:940` `has_documents` 判素材库 reference materials（`Material.is_reference`），`agent.py:949` `missing_chapters` 判知识库文档，两套源 → 自相矛盾。
- **改**：`agent.py:940-967` 话术区分——`has_documents=False` 时改"未选择额外参考素材，将使用知识库 N 个文档生成"（语义对齐，**不改判断逻辑**）。

### 节点4 — 记忆服务 NoneType
- **根因**：`memory_service.py:149` `session_id[:8]`，请求未传 session_id → None → NoneType not subscriptable。
- **改**：`agent.py:1527 _save_memory` 开头 `if not session_id: return`（双保险 `memory_service.py:149` 防御）。

## 禁区
- 不改 derive 强节点 4 约束设计（溯源/边界/原文优先/待补）
- 不重构生成主路径（G19a 先行 / G25a perstep 不动）
- 不碰 colspan 表格展开（已修）
- 不做新功能 / 多专业扩展

## 验证
- 节点1：重启后端 → 重跑生成 → 日志无 `derive_strong_failed`；diagnose_all_chapters 列表章节填充率回升
- 节点2：日志出现 `g22a_process_card_steps_injected`；G22a step_desc 直填工序名短词
- 节点3：分析报告话术不再矛盾
- 节点4：日志无"异步摘要保存失败"
- 全量：pytest 0 failed（baseline 674 passed）；web 端到端生成可用
- 收尾：清临时 diagnose 文件 + DEV-LOG done + 经验回流 wiki

## 执行约定
- 业务代码走 Writer subagent（lead 不直接 Edit/Write 业务代码）；节点1/3/4 极小可合并一个 Writer，节点2 diagnose 后单独
- 出错暂停（task_state: paused），不硬撑
- 修完重启后端（exp：别信 reload），顺带验 feedback-rules 节点6（归属 feedback-rules）

## 关键文件
- `backend/app/agents/functional/writing_agent.py`（节点1 :1440；节点2 G22a直填 :888-905）
- `backend/app/agents/orchestrator/orchestrator.py`（节点2 :2780-2803；derive强节点 :895-937）
- `backend/app/api/agent.py`（节点3 :940-967；节点4 :1527）
- `backend/app/services/memory_service.py`（节点4 :149）
- `backend/app/services/hierarchical_context.py`（extract_process_card_steps :1703；get_all_chapter_indexes :1450）
