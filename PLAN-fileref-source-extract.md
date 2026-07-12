# PLAN: G5a 引(借)用文件目录 从源 extract 直填（绕过 derive 串源）

> slug: `fileref-source-extract` · 承接 `ALIGN-fileref-source-extract.md` · seal 后不可变

## Context（为什么改）

web 验收（2026-07-12）发现：生成 `documents/1` 时，G5a「引(借)用文件目录」的「文件名称」列填的是**零部组件名**（六舱/尾焰挡板组件），而非素材里的引用文件（`《导弹产品规范》`等）。

根因：G5a 无专门 extract → `filled_data` 空 → 触发 `derive_list_strong` 从 G25a 装配卡倒推，通用 derive prompt（writing_agent:1316「归纳零件、设备、材料」）把 G5a 当零件清单 → 零部组件名塞进「文件名称」列。同类前科 G18a（2026-07-11 已修，但 G5a 不能照搬 catalog 补丁——material_catalog 不含引用文件）。`exp-derive-strong-node.md` 待办第 3 条早已标记 G5a 待排查。

预期结果：G5a 表填素材里的 5 个引用文件，代号-文件名称配对正确，无零部组件名。

## 方案（source-driven extract 直填，复用 G22a 模式）

G5a 的源表格已在 source-driven-fix 贯通：`chapter_index` 定位 page 3 / doc_dir="1"，`hierarchical_context._html_to_readable`（:1240）把 HTML 表转 Markdown pipe 表，**source_text 含完整 `| 序号 | 代号 | 文件名称 | 页数 | 备注 |` + 5 行**。照 G22a/G25a 的「源 extract → params 注入 → writing_agent 直填」模式给 G5a 接一套。

## 改动清单

### 节点1：新增 `extract_file_references`（hierarchical_context）

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/hierarchical_context.py` | 新增 `extract_file_references(doc_dir_name) -> List[Dict]`，紧邻 `extract_process_steps`（:1468）。照 `extract_process_steps` 模式：`get_chapter_content(doc_dir, "引(借)用文件目录")` 拿 Markdown → 按行 split → 识别数据行（首列是数字序号 1-5）→ 按列位置抠 `seq/ref_code/ref_name/pages/remarks` → 返回 `[{seq,ref_code,ref_name,pages,remarks}, ...]`。过滤表头/分隔行/产品信息区/会签行（复用 `extract_process_steps` 的 `header_words` 思路）。源缺失/解析空 → 返回 `[]`。 |
| `backend/tests/test_hierarchical_context.py`（或同级测试） | 单测：①documents/1 真实 G5a 抠出 5 行（ref_name 含「导弹产品规范」等，无零件名）②源缺失返 `[]` ③非数据行（表头/会签）被过滤。 |

**节点1 第一步**：先 `print` 一次 G5a 的 `get_chapter_content("1","引(借)用文件目录")` 实证 Markdown 列顺序（colspan 展开后确认是 序号/代号/文件名称/页数/备注），再写解析。

### 节点2：G5a 注入 + 消费 + derive 排除

| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/orchestrator/orchestrator.py` | ① **注入**：在 G22a 注入块（:2846-2872）之后，照写 G5a 块——遍历 `phase_task_indices` 找 `chapter_code=="G5a"` → 从 `missing_chapters` 查 `_doc_dir`（同 G22a:2854）→ `hierarchical_context.extract_file_references(doc_dir)` → `tasks[idx]["params"]["file_references"] = file_refs` + `logger.info("g5a_file_refs_injected")`，try/except `logger.warning("g5a_file_refs_failed")`。② **derive 排除**：`LIST_CHAPTERS`（:913）删 `"G5a"` → `{"G4a","G10a","G12a","G14a","B12a","G18a"}`（LIST_CHAPTERS 仅 :918 一处引用，删 G5a 只影响 G5a 不再倒推，无副作用）。 |
| `backend/app/agents/functional/writing_agent.py` | **消费**：在 G22a 消费块（:874-891）之后，照写 G5a 块——`_refs = task.get("params",{}).get("file_references")`；`if chapter_code=="G5a" and _refs:` → 填 `structured_values["seq"]/["ref_code"]/["ref_name"]/["pages"]/["remarks"]`（每个是 list，按行对齐）+ `struct_row_count=len(_refs)` + `ref_name` 从 `unstructured_cols` 移除（直填不交 LLM，同 G22a `step_desc`:891）。 |
| `backend/tests/test_orchestrator_derive.py`（或同级） | 追加：G5a 不在 LIST_CHAPTERS 后 `_derive_strong_node` 跳过 G5a（不断言倒推）。 |

### 节点3：web 验收 + 全量回归

- web 生成 `documents/1`，G5a「文件名称」列 = 素材 5 个引用文件（小产品/《空中制导…》/《导弹产品规范》/《导弹运载火箭…》/《导弹装配工艺规范》），无零部组件名。产物入 `.test-runs/fileref-source-extract/`。
- `cd backend && python -m pytest tests/ -q`（基线 679 passed 0 failed 不回归）。

## 禁区

- `_derive_list_from_upstream` 通用倒推 prompt（writing_agent:1316）—— 不改，只通过 LIST_CHAPTERS 排除 G5a。
- 其他 LIST_CHAPTERS（G4a/G10a/G12a/G14a/B12a/G18a）的 derive —— 不动。
- `_merge_derived_rows`（:988）/ `_enrich_names_from_catalog`（:1014，G18a 专属）—— 不碰。
- writing_agent `_do_template_fill` 通用 slot 兜底逻辑 —— **不加**全局"待补"标注（避免污染通用路径）。G5a extract 失败时由 source-driven 注入的 source_text 兜底（LLM 照源填 ref_name，源里是文件名不会串零件），极端空则接受留空（用户已决策）。
- extract 落库链（`KnowledgeExtractor.extract_and_save`）—— 不扩展（引用文件不落 material_catalog）。
- G4a（工艺文件目录）—— 本期不修（用户决策，单列后续）。
- 前端 —— 不改。

## 验证

1. `cd backend && python -m pytest tests/test_hierarchical_context.py tests/test_orchestrator_derive.py -v`（节点1/2 单测全绿）
2. `cd backend && python -m pytest tests/ -q`（全量回归，≥679 passed 0 failed）
3. web 端 project=documents/1 生成，G5a 表抽样：代号-文件名称配对正确、无零部组件名（playwright dump 或截图入 `.test-runs/fileref-source-extract/`）
4. 日志确认：`g5a_file_refs_injected` 出现 + 无 `derive_strong_failed` + G5a 不触发 derive 倒推

## 节点拆分（执行 loop）

1. **节点1**：`extract_file_references` + 单测（commit `feat`）
2. **节点2**：orchestrator 注入 + writing_agent 消费 + LIST_CHAPTERS 排除 + 单测（commit `feat`/`fix`）
3. **节点3**：web 验收 + 全量回归（commit `chore`/`test`）

## 执行约定

- seal：项目仓库 `git commit -m "plan: fileref-source-extract seal"`
- 业务代码照 G22a 模式简单直接改（每节点 1-2 文件）
- 进 loop 第一件事 `/devlog-update localknowledgebase-word` 写 running + task_slug
- 出错暂停（lead.md 第 6 步），不硬撑
