# 需求对齐卡：G5a 引(借)用文件目录 从源 extract 直填（绕过 derive 串源）

## 现象（web 验收 2026-07-12）

生成 `documents/1`，G5a「引(借)用文件目录」表的「文件名称」列填的是**零部组件名**（六舱/尾焰挡板组件等），而非素材里的引用文件/规范名。

素材 G5a 真实数据（page 3 源 HTML）：
- 列：`序号｜代号｜文件名称｜页数｜备注`
- 5 行：①小产品 ②《空中制导试验导弹整体流程(KZD)》 ③《导弹产品规范(KZD)》 ④《导弹运载火箭电气和电子设备安装通用技术条件》 ⑤《导弹装配工艺规范》

## 根因

1. **G5a 无专门 extract**：`structured_extractor.py` 全文无 `file_ref`；`knowledge_extractor.py:72` 只有分类用 TITLE_PATTERN，**无数据行提取函数**。`extract_and_save` 落的是 MaterialCatalog/ProcessStep（零部件/工序），不含引用文件。
2. → G5a `filled_data`（original）为空。
3. → G5a ∈ `LIST_CHAPTERS`，触发 `derive_list_strong` → `_derive_list_from_upstream`（writing_agent）。
4. derive prompt 通用（"从上游工序归纳零件、设备、材料"），把 G5a 当零件清单从 G25a 倒推 → 零部组件名塞进「文件名称」列。
5. `original-first merge` 没挡住（original 本来就空）。

> 同类前科：G18a 配套表 derive 错位（2026-07-11 g18a-g14a-name-fix 已修，用 catalog exact 查）。但 **G5a 不能照搬**——material_catalog 不含引用文件。`exp-derive-strong-node.md` 待办第 3 条早已标记 G5a 待排查。

## 目标

- **解决谁的什么问题**：用户生成的工艺文件，G5a 该列引用文件却列了零件，误导验收、文件不可用。
- **成功长什么样**（可观察）：
  - web 生成 `documents/1`，G5a「文件名称」列 = 素材里的 5 个引用文件（小产品/《空中制导…》/《导弹产品规范》/《导弹运载火箭…》/《导弹装配工艺规范》），代号-文件名称配对正确。
  - G5a 表内**无零部组件名**（六舱/尾焰挡板组件等不出现）。
  - 后端 pytest 全绿（基线 679 passed 0 failed）。
  - 日志无 `derive_strong_failed`、G5a 不再走 derive 倒推填零件。

## 边界

### 做
- 给 `file_ref`(G5a) 加**从源 extract 数据行**逻辑：定位 G5a 章节 source_text（chapter_index 已有 page 3 / doc_dir="1"），抠出序号/代号/文件名称/页数/备注数据行，直填 `filled_data`。
- 复用现有 source-driven 注入链路（同 G19a `extract_process_steps` / G22a `process_card_steps` 模式：从源抠 → 直填 → 绕过 derive）。
- 单测覆盖（抠取正确 / 源缺失容错 / 列对齐）。

### 不做
- 不改 derive 通用倒推逻辑（G10a/G12a/B12a/G18a 的 derive 不动）——见模糊点 3 的兜底决策。
- 不落库 material_catalog（引用文件不需 SQL 查询，生成时从源抠即够）。
- 不改前端（G5a 渲染沿用现有 list 章节 UI）。
- 不动 extract 落库链（KnowledgeExtractor.extract_and_save 不扩 file_ref 落库）。

## 模糊点（待对齐清零）

1. **【scope】✅ 已澄清（用户 2026-07-12）**：**本期只修 G5a（file_ref）**，G4a 单列后续。G4a 表头更复杂（多级表头 + 双层列 + 零部件列有意义），需独立设计，避免 scope 膨胀。
2. **【数据源】extract 从哪抠？** —— 倾向：G5a 章节 source_text（chapter_index 定位的源 HTML，已在 source-driven-fix 贯通）。PLAN 探索阶段实证 source_text 是否真含 G5a 表格 HTML。若空 → 先修注入（同 G22a 9b-2 模式）。
3. **【兜底】✅ 已澄清（用户 2026-07-12）**：**extract 失败则 G5a 留空/待补，不走 derive**。G5a derive 倒推本质是错的（装配卡里没有引用文件信息），兜底也是坑。→ 实现上：在 derive 排除清单（`_derive_strong_node` 的 LIST_CHAPTERS 或 `derive_list_strong`）加 G5a，让 G5a 永不倒推；extract 直填成功则有内容，失败则 slot 走原有"待补"标注。
4. **【鲁棒性】「文件名称」边界界定**：素材行①"小产品"是产品名混在引用里、②~⑤带书名号《》。extract 怎么界定文件名（按列位置 vs 按书名号）？—— 技术细节，PLAN 探索定（倾向按表格列位置抠，不依赖书名号）。

## 下游

- → 进 PLAN（同 slug `fileref-source-extract`），PlanMode 实证 source_text + 定 extract 实现 + 拆节点。
