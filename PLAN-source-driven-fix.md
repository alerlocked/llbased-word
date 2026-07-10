# PLAN: source-driven 生成链路贯通（slug: `source-driven-fix`）

> 项目: localknowledgebase-word | seal: 2026-07-10 | 承接 `ALIGN-source-driven-fix.md`
> seal 后不可变，进度记 DEV-LOG/git。

## Context

gen-quality-fix 节点②深挖铁证：4 次生成 `chapter_indexes_count=0`（知识库文档未索引）→ orchestrator.py:1625 所有章节 `source_text=""` → **无源生成、LLM 凭空编**，这是用户"生成没到位"的真因。同时 `assembly_process_template.json:308` 的 `process_steps` 硬编码经查是**死代码**（无任何代码读取，G19a 主路径是 `extract_process_steps` orchestrator.py:2838 + LLM fallback），违背"每次从上传文件 extract 工序"原则，用户明确禁止硬编码冒充标准。

本 PLAN：删 process_steps 死代码 + 让"上传工艺文件 → 完整索引 → extract 真实工序 → 有源生成"链路贯通，按工艺文件验收标准（extract 版）达标。

## 根因（已定位）

1. **process_steps 死代码**（`assembly_process_template.json:308-324`）：commit `0e8fe19`(06-06) 初始模板遗留，`f747293` source-driven 后无人读。G19a 实际走 `extract_process_steps`（orchestrator.py:2838，从上传文件 G19a 章节 extract）+ LLM fallback，**不 fallback 到模板硬编码**。
2. **文档索引断裂 = 数据状态**：`materials` 表空、`documents/1/` 全空（4 月解析过的 QJ903 产物被清）、全单电缆装配规程.pdf 在 `data/process_docs/` 未走上传索引 → `chapter_indexes=0`。上传链路：`creation.py:1309 建 Material → :1328 入 pdf_queue → document_processor.py:142 解析(产物 content.html/index.json/pages) → document_indexer.py:60 build_index 写 chapter_index.json`。`generate_document_html` 模块在位（项目根/scripts，SCRIPTS_DIR 指向正确）。

## 改动清单

### 节点1 — 删 process_steps 死代码（确定，纯减法）
- `backend/app/templates/assembly_process_template.json`：删 `process_steps` 段（:308-324）
- 验证：`grep -rn process_steps backend/app/`（应只剩 DB 表 process_steps 的 ORM，无模板字段引用）；G19a 生成仍走 extract（orchestrator.py:2838 不变）

### 节点2 — 重新上传工艺文件 + 诊断/修索引链路（运行时驱动）
- 走上传 API（`creation.py` upload）上传 `data/process_docs/全单电缆装配规程.pdf` → 触发完整解析队列
- **诊断锚点**：① materials 表新增记录 ② `documents/{id}/` 完整(content.html/index.json/chapter_index.json/pages) ③ `chapter_indexes > 0` ④ `extract_process_steps` 返回真实工序
- **若断裂按断点修**（候选，运行时定位）：`_get_all_documents` 文件系统分支读 `index.json`(:218) vs `chapter_index.json`(:247/:1110) 文件名不一致 / chapter_index.json 没建(build_index 没触发) / 解析不完整(content.html 缺)

### 节点3 — 贯通 source-driven + 按验收标准验收
- 上传完整索引后 web 生成：G19a extract 真实工序 → G18a/G22a/G25a 行数对齐 → 各章有源生成
- 按工艺文件验收标准（extract 版）逐项过

## 禁区
- 不改 11 章节模板结构 / 不重写生成主路径 / G19a 必须走 extract 不引入新硬编码 / 不碰 colspan/derive 4 约束

## 关键文件
- `backend/app/templates/assembly_process_template.json`（节点1 删 :308-324）
- `backend/app/api/creation.py`（节点2 上传 :1235-1370）
- `backend/app/services/document_processor.py`（节点2 解析 :142）/ `document_indexer.py`（chapter_index :60）
- `backend/app/services/hierarchical_context.py`（_get_all_documents :177 / get_all_chapter_indexes :1450 / extract_process_steps :1468 / 文件名 :218 vs :247/:1110）
- `backend/app/agents/orchestrator/orchestrator.py`（G19a extract :2838 / 章节源 :1617-1683）

## 验证
1. 节点1：grep process_steps 无模板引用 + pytest 0 failed
2. 节点2：上传 → `chapter_indexes > 0` + `extract_process_steps` 非空
3. 节点3：web 生成 → 验收清单逐项过 + 日志无 `chapter_indexes_count=0`/`derive_strong_failed`
4. 收尾：清 g22a_doc_dir_diagnose 临时日志 + DEV-LOG done + 经验回流（文档索引断裂根因 + process_steps 死代码 + 验收标准 extract 版）

## 执行约定
- seal：本文件 git commit `plan: source-driven-fix seal`
- 节点1 直接改；节点2 运行时诊断驱动；节点3 验收。业务代码走 Writer subagent。出错暂停。
