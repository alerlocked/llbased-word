# PLAN: G4a 工艺文件目录 source-driven extract

> slug: `g4a-source-extract` · 对应 TODO.md #2(P0 挡交付质量)
> 照 G5a `fileref-source-extract` 三件套套路。关联 exp:`exp-fileref-source-extract`(警告 G4a 独立设计)、`exp-dual-header-extract`(双层列头)。

## Context

G4a(工艺文件目录 = 本文件自身的章节目录)目前走 derive 倒推(`LIST_CHAPTERS` 含 G4a,orchestrator.py:913),从 G25a 反推填表 → "零部组件代号/名称"列被串成零件名,且双层列头漏抽。和已修的 G5a(`fileref-source-extract`)、G12a/G14a(`extract-fields-fix` v2)同根因。

源 `documents/1/content.html` 第 2 页 G4a 表里 **10 行目录条目齐全**(引借用文件目录/工艺过程卡/装配工艺卡片…+真实页数 1/4/2/30/9),可 source-driven 直填。G4a 源"零部组件"列恒为产品本身(`KA0-0-KZD/小产品`)非零件,derive 倒推必串。

**验收(用户已定 A)**:前端生成 G4a,10 行目录条目全从源直填(序号/文件名称=章节名/文件编号/零部组件代号+名称=产品本身/页数/册数/备注),零臆造、零串零件。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/hierarchical_context.py` | **新增 `extract_doc_catalog(doc_dir_name, text)`**(照 `extract_file_references`:1509 模式):`get_chapter_content(doc_dir,"工艺文件目录")` 定位 → 解析双层列头(**锚点用"编号"+"代号"同时出现的行**,因 G4a 有两个"名称"列歧义,不用 G5a 的"序号+文件名称")→ 序号正则 `^[1-9]\d{0,2}$` 过滤数据行(拒日期签名行)→ 返回 `List[{seq,doc_name,doc_number,component_code,component_name,pages,volume,remarks}]`。两个"名称"列按位置区分(第1个=doc_name 文件名称,第2个=component_name 零部组件名称)。 |
| `backend/app/agents/orchestrator/orchestrator.py` | ① `LIST_CHAPTERS`(913)删 `"G4a"`(照 G5a 排除注释加 G4a);② **G5a 注入段(2874-2901)后照搬一段 G4a 注入**:遍历 phase_task_indices 找 G4a → missing_chapters 按 title 反查 `_doc_dir` → `extract_doc_catalog(doc_dir)` → 填 `tasks[idx]["params"]["doc_catalog"]`;`_doc_dir` 空时 `logger.warning("g4a_no_doc_dir_fallback")`(与 g5a 同款)。 |
| `backend/app/agents/functional/writing_agent.py` | **G5a 消费段(893-904)后照搬一段 G4a 消费**:读 `doc_catalog` → 直填 `structured_values` 8 列(seq/doc_name/doc_number/component_code/component_name/pages/volume/remarks)→ `struct_row_count=len` → `doc_name` 从 `unstructured_cols` 移除(防 LLM 臆造章节名)。 |
| `backend/tests/...` | 新增单测:`extract_doc_catalog` 喂真实 `documents/1` G4a,断言抠出 10 行 + 字段对(文件名称=章节名、零部组件=KA0-0-KZD/小产品、页数含 30/9 等);derive 不再处理 G4a 的断言。 |

## 禁区

- 不动 G5a 的 `extract_file_references`/注入/消费逻辑(G5a 已稳)
- 不动前端、不动其他章节(G10a/G12a/G14a/G18a 等)
- 不碰双层列头网格轴深修(`_expand_table_grid` colspan 起点偏移,如 unit=0 同类,影响小留后续)
- 不动 derive 主链路(`_derive_strong_node`/`_merge_derived_rows`),只把 G4a 从 `LIST_CHAPTERS` 摘出

## 复用(现有,不新造)

- `hierarchical_context.extract_file_references`(hierarchical_context.py:1509)— 模式照搬
- orchestrator G5a 注入段(orchestrator.py:2874-2901)— 模式照搬
- writing_agent G5a 消费段(writing_agent.py:893-904)— 模式照搬
- `get_chapter_content(doc_dir, chapter_title)` — 章节定位
- 序号正则 `^[1-9]\d{0,2}$` — 数据行过滤

## 验证

1. **单测**:`pytest backend/tests/ -k "doc_catalog or g4a" -v` — extract 10 行 + 字段对 + derive 不碰 G4a
2. **全量回归**:`pytest backend/tests/` — 0 failed 不回归(基线 670 passed)
3. **端到端(用户验收)**:起后端,web 生成,G4a 目录表 10 行直填
4. 收尾:`#10 profile 注入日志` / `#9 diagnose 脚本恢复` 按 TODO 顺手带

## 内网同步(明天,本 lead 范围外)

本 lead commit 后,明天 sync localkb→kylin 自动带上 G4a 修复。内网机日志的 `g5a_no_doc_dir_fallback` 是源没准备,明天跑补齐工作流 + 重启清缓存解决。
