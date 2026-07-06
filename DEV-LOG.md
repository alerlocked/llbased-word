---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-07-05T23:30:00+08:00
last_commit: 529c4b8
status: revive-extract-funnel 完成（Step 2 F 落库链复活，落库+查询通）
task_state: done
task_slug: revive-extract-funnel
---

<!--AUTO:GIT-->
## 最近变更
- `529c4b8` chore(devlog): revive-extract-funnel done (Step 2 F 落库链复活完成) (0 seconds ago)
- `ed24188` feat(search): C knowledge_search 恢复真 ORM 查询（节点4） (7 minutes ago)
- `320ad3c` feat(doc-processor): 解析后触发 KnowledgeExtractor + StandardExtractor（节点3） (8 minutes ago)
- `1e558f1` feat(extract): extract_and_save 维度传递 specialty（节点2） (10 minutes ago)
- `8241207` feat(db): 补 6 结构化 ORM + specialty 迁移（节点1） (12 minutes ago)
- `7269bd7` plan: revive-extract-funnel (Step 2 复活 F 落库链) seal (14 minutes ago)
- `1a01091` chore(devlog): cleanup-and-dimensions done (Step 0+1 完成) (2 hours ago)
- `c31cf0b` feat(api): material GET 加 model/specialty + PUT 更新 API + CLAUDE.md 去向量（节点5 后端） (2 hours ago)
- `7e9d25f` feat(retrieval): HierarchicalContext 型号/专业 filter 穿透（节点4） (2 hours ago)
- `1f71182` feat(upload): LLM 推断 model/specialty 写 Material（节点3） (2 hours ago)
<!--/AUTO:GIT-->

## 当前状态
- **完成**：revive-extract-funnel（Step 2 复活 F 落库链）—— 节点1✅ 补 6 ORM（MaterialCatalog/ProcessStep/Standard/StandardClause/StepMaterial/StepTool 对齐 craftdoc.db）+ specialty 迁移；节点2✅ extract_and_save 维度传递（Material.specialty → MaterialCatalog/ProcessStep，实测 13 行带 assembly）；节点3✅ document_processor 解析后 try-except 触发 KnowledgeExtractor + StandardExtractor（QJ903 检测）；节点4✅ C knowledge_search 6 函数恢复真 ORM 查询（search_materials(螺钉) 返真实物料）；节点5✅ 验证：extract_and_save('1') 落 58 物料+11 工序 + pytest 667 passed（仅 draft flaky 预存）。**关联落库（StepMaterial/StepTool）留 Step 3/4**。待用户开 Step 3/4。
- **完成**：cleanup-and-dimensions（Step 0 清噪 + Step 1 型号专业维度）—— 节点1✅ 删 6 死壳（SearchAgent/IndexingService/UnifiedRetrieval/KnowledgeGraph/VectorStore/api-rag，净删 3638 行）+ C stub + writing_agent 走 HierarchicalContext；节点2✅ Material 加 model/specialty + 迁移；节点3✅ material_classifier LLM 推断（上传时写，实测 assembly/welding/machining 准）；节点4✅ HierarchicalContext filter 穿透（_get_all_documents/search_tables/global_keyword_search 加 filters）；节点5✅ CLAUDE.md 去向量 + GET/PUT material API。**前端 UI（AddMaterialDialog specialty 下拉+model 输入）待后续**。节点6✅ pytest 全量无新 fail（667 passed，仅 draft flaky 摆动 0-2 预存）。待用户开 Step 2/3/4。
- **完成**：derive-strong-node（倒推强节点）—— 节点1✅ `_provenance_filter`（溯源校验，丢弃 G25a 无出处条目）+ 节点2✅ orchestrator `_derive_strong_node`（generated_chapters 后/Review 前无条件倒推，原文优先合并 + 待补标注）+ 节点3✅ 移除 writing_agent 三空弱兜底 + 节点4✅ pytest 全量回归 0 failed（683 passed）。**附带修复测试隔离**：test_registry snapshot/restore（registry 全局单例 clear 不恢复）+ conftest autouse `mock.patch.stopall+GC`（根治 draft_service 跨测试 async mock 残留 flaky）。**documents/1 web 验收待用户**（行数对比+抽样核对 G25a 出处+待补字段）。
- **完成**：content-detail —— G25a content 详实化三节点全过。① 节点1 _table_to_markdown colspan 网格展开(extract op5 9→729字/ASM 1134→4992,三层根因)② 节点2 生成 prompt 详实化(content_avg 32→461字,零臆造)③ 节点3 装配卡说明(extract_assembly_overview 769字+注入)。待用户 web 验证;后续重跑 diagnose_all_chapters 看其他章节是否受益 + G14a/G12a 逐章
- **历史完成**：content-quality(检验收紧38→5+实证) + contract-align(检验行+契约guard+docx2pdf)
- **历史完成**：contract-align（检验工序行+契约guard+docx2pdf中文路径）三节点全过
- **节点A✅**：G25a 检验工序行（方案Y merge 后处理）。LLM 照常生成 content+inspection，_expand_inspection_rows 拆检验行插入；模板删 inspection 列。diagnose 40rows=10操作+30检验，检验行 step_name=检验，复杂工序多点/简单单点。commit 2b2b009
- **节点B✅**：前后端 column-key 契约校验 guard（scripts/hooks/guard-column-align.py，PostToolUse warn）。对比模板 key vs layout key，G10a/G14a/G12a 白名单，dual_list/flow_chart 跳过，路径过滤。3 项验证过。父 repo e2d5b28
- **节点C✅**：docx2pdf 修复。根因=Word COM 对中文路径 Open 卡死；解法=staging 到 ASCII temp dir + win32com 优先。中文路径端到端 PDF 306KB 产出。父 repo 709b624
- **待用户**：web 端 project=2 装配卡刷新确认检验行渲染（后端 diagnose 已实证 filled_data 含检验行）
- **历史**：g25a-perstep 已完成（A✅B✅C✅ web 验证）；g25a-write 已落地

## 关键决策
- **G25a 检验=单独工序行（用户定+截图验证）**：检验不单独成列（前端不加列），后端生成检验工序行（step_name=检验），贴合真实工艺文件格式。方案Y（merge 后处理）不动 g25a-perstep 并行核心
- **前后端契约校验=guard hook（用户定）**：PostToolUse warn 脚本对比模板 key vs layout key；G10a/G14a/G12a 历史不一致白名单兜底（KNOWN_DIFFS），本次不修，TODO 单独排期
- **docx2pdf 中文路径=Word COM 卡死根因**：Word.Application COM Open/SaveAs 对非 ASCII 路径卡死/URL 编码 %20；解法=staging 到 ASCII temp dir 转换再复制出（纯文件复制不怕中文）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好
- **参数参考值=triples 兜底**（用户定）：工步原文优先，绝不臆造
