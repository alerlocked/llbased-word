# 需求对齐卡:G4a 工艺文件目录 source-driven extract

> slug: `g4a-source-extract` · 对应 TODO.md #2(P0 挡交付质量)
> 照 G5a `fileref-source-extract` 套路,G4a 专用 source extract。exp `exp-fileref-source-extract` 已警告"G4a 独立设计,不能照搬 G5a"。

## 现状诊断(探索结论)

- **G4a = 工艺文件目录**(本文件自身的章节目录),模板 `assembly_process_template.json:49-63`,8 列:`seq/doc_name/doc_number/component_code/component_name/pages/volume/remarks`,`table_type=single_row_list`
- **源**(`documents/1/content.html` 第 2 页 G4a 表):双层列头(`工艺文件`大列分 名称/编号;`零部组件`大列分 代号/名称;+页数+册数+备注),10 行目录条目齐全
- **病根**:G4a 在 `LIST_CHAPTERS`(orchestrator.py:913)→ 被 derive 倒推 → "零部组件"列从 G25a 串零件名;且双层列头 `_extract_tabular_fields` 列映射偏移漏抽(同 G12a/G14a,extract-fields-fix v2 修过同类)
- **关键差异 vs G5a**:G4a 源里"零部组件代号/名称"恒为产品本身(`KA0-0-KZD/小产品`)**不是零件**;G4a 8 列(G5a 5 列),双层列头更复杂

## 目标

- **解决谁的什么问题**:工艺文件生成质量。G4a 现在走 derive 倒推 + 双层列头漏抽 → 目录条目错(串零件)/缺。
- **成功长什么样**:前端生成 G4a,10 行目录条目从源直填(序号/文件名称=章节名/文件编号/零部组件代号/名称=产品本身/页数/册数/备注),不串零件、不臆造。

## 边界

- **做**:照 G5a 三件套——`hierarchical_context.extract_doc_catalog`(G4a 专用,处理双层列头列定位)+ orchestrator G4a 分支注入 + writing_agent G4a 消费直填 + `LIST_CHAPTERS` 删 G4a 不倒推
- **不做**:G4a 双层列头网格轴深修(如 unit=0 同类,影响小);其他章节不动;不碰 G5a 已有逻辑;不动前端

## 模糊点

- [已确认] **验收标准 = A**:10 行目录条目全从源直填(文件名称=章节名/文件编号/零部组件代号/名称=产品本身/页数/册数/备注),零臆造、零串零件(和 G5a 口径一致)
- [已定] 方案 = 完全 source-driven 直填(零 LLM),和 G5a 一致
- [已定] G4a vs G5a 差异已厘清(列数/双层列头/零部组件=产品本身非零件)
- [接受的不确定性] 源里部分序号在 colspan 单元格内位置错位(`<td colspan="2"></td><td>5</td>`),extract 需处理,属实现细节,PLAN 阶段定

## 下游

- → 进 PLAN(slug: `g4a-source-extract`)
