# 需求对齐卡：G5a/G12a/G14a extract 逐章提质（TODO P0 #1）

## 背景
gen-test-fixes #1 归档确诊：G5a/G12a/G14a `structured_extraction_done` 的 fields_found 低（源有内容没抽全）。实证 `documents/1` content.html table3(G5a)/table6(G12a)/table7(G14a) 均为**双层列头(colspan/rowspan)复杂表**，`_extract_tabular_fields` 列映射偏移；G5a 首条"文件名称=小产品"系产品区串入。本卡对齐逐章提质的范围/方案/验收。

## 目标
- **解决**：G5a/G12a/G14a 从源文档 extract 抽全结构化字段（fields_found 反映源实际行数），下游生成内容质量提升
- **成功（可观察）**：
  - 三章 `structured_extraction_done` 的 fields_found 对齐源实际数据行数（G5a ref_name≈源引用文件行数 / G12a quota≈源材料定额数 / G14a material_desc≈源辅材数）
  - 真实生成 web 验收：三章表格内容详实、无产品区串入
  - pytest 不回归

## 边界
- **做**：G5a/G12a/G14a 三章 extract 修复（列映射 / colspan 展开，改法定于 PlanMode）
- **不做**：
  - G4a（TODO #2，同根但双层列更复杂，**后续单独 lead**）
  - 不动生成 prompt / writing_agent 生成逻辑
  - 不动前端 layout / column-key（那是 TODO #3）
  - 不动 derive 倒推
- **范围**：仅 `documents/1` 类双层列头清单表的 extract 链路

## 模糊点（PlanMode 探索后定）
- **[待查·核心] 改法分叉**：
  - (A) 改 `_extract_tabular_fields` 列映射（精准针对双层列头，按"序号+目标列名"动态定位）
  - (B) 改上游 `_table_to_markdown` colspan 网格展开（通用，exp §1.10 已修一轮——**为何没覆盖这 3 章？要查**）
  - (C) 两者结合
- **[待查]** G5a 产品区串入（"文件名称=小产品"）：是 extract 列映射偏移，还是 source 取段（`knowledge_context`）本身就含产品区
- **[已定·用户拍]** 三章**同批改**（G5a+G12a+G14a 一起改），**不逐章 stop-and-test**；三章全改完后**一次性** web 验收
- **[接受]** 验收手段：每章 extract 单测进 `tests/`（pytest 一次跑全）+ 三章改完后**一次**真实生成 web 验收（diagnose 脚本已清，见 TODO #9）

## 下游
- → 进 PLAN（slug=`extract-fields-fix`），PlanMode 读 `structured_extractor._extract_tabular_fields` + `hierarchical_context._table_to_markdown` 现状，定改法（A/B/C）后 seal
