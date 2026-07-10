---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-07-10T22:16:35+08:00
last_commit: 2c0602d
status: source-driven-fix 执行中（文档索引断裂 + extract 链路贯通）
task_state: running
task_slug: source-driven-fix
---

<!--AUTO:GIT-->
## 最近变更
- `2c0602d` fix(g22a): fill doc_dir from chapter_indexes when adding template chapters (0 seconds ago)
- `0d50176` chore(template): remove dead process_steps hardcoded steps (source-driven-fix node1) (4 hours ago)
- `d4463fa` plan: source-driven-fix seal (4 hours ago)
- `4b1c1f3` chore: wrap gen-quality-fix (node 1/3/4 verified, node 2 -> source-driven-fix) + ALIGN source-driven-fix (22 hours ago)
- `54c3304` fix(generation): distinguish 素材库 vs 知识库 wording + guard memory NoneType (25 hours ago)
- `23731d0` diag(g22a): log chapter_title + missing_chapters doc_dir to locate injection fallback (25 hours ago)
- `701e1f3` fix(generation): add TemplateColumn import in derive_list_strong — fixes 6 empty list chapters (25 hours ago)
- `1fc7d68` plan: gen-quality-fix seal (25 hours ago)
- `bc84740` fix(doc-processor): remove redundant Material import causing UnboundLocalError (2 days ago)
- `ac5d6f0` feat(feedback): rule review UI in ProfilePage (node 5) (3 days ago)
<!--/AUTO:GIT-->

## 当前状态
- **完成（gen-quality-fix, PLAN 1fc7d68）**：节点① derive import + ③ 话术 + ④ NoneType 代码改完**运行时验证通过**（日志 derive_strong_failed/异步摘要失败均消失，baseline pytest 674 passed）。节点② G22a 深挖定位真因=**文档索引断裂**（chapter_indexes_count=0 → orchestrator.py:1625 所有章节 source_text="" 无源生成），超本 lead 范围，**转移 source-driven-fix**。diagnose 日志 g22a_doc_dir_diagnose（23731d0）待 source-driven-fix 验证后清。
- **进行中（source-driven-fix, ALIGN 已写待 PLAN seal）**：修文档索引链路（chapter_indexes>0）+ G19a 从上传文件 extract 真实工序（清/降级 template process_steps 硬编码）+ 贯通 source-driven 有源生成，按工艺文件验收标准（extract 版）达标。PlanMode 查根因中。
- **完成（feedback-rules, PLAN d6d946c）**：节点1✅ 撤 standard-enforce（commit 2623e04）+ 节点3✅ 后端 FeedbackLearner（services/feedback_learner.py：learn_from_edits async + LLM 归纳 prompt + _rule_based_fallback 同列重复 old→new 产 terminology 规则 + 三层 fail-soft，产 Principle source=feedback_learned/enabled=False 待审）+ api/profile.py 加 LearnFeedbackRequest/CellEditItem/RowChangeItem/PrinciplePatchRequest + POST /learn-feedback（add_principle 幂等）+ PATCH /principles/{id}；import ok + pytest test_feedback_learner 5 passed。节点4a✅ 前端原始快照（creationStore 加 originalTemplateData + 抽 utils/templateTransform.ts util + AIChatPanel 生成时 setOriginalTemplateData 快照 + WorkspacePage 复用 util/项目切换清快照/删 dead mapTableType，tsc 0 错）。节点4b✅ 前端 diff 采集（utils/templateDiff.ts：业务键行对齐+cell diff+无键行数不同走集 diff 避免错位；handleSave 算 diff 静默 POST /api/profile/assembly/learn-feedback fail-soft，基准=originalTemplateData，空 diff 不 POST + add_principle 幂等，tsc 0 错）。节点5✅ 规则审查 UI（ProfilePage principles Tab：feedback_learned/待审置顶排序 + 来源列 + 启用 Switch（PATCH enabled）+ 候选计数提示；handleTogglePrinciple；sourceLabel 兜底空 source→内置，后端补 source=builtin 非必要跳过；tsc 0 错）。节点6 自动化验证✅：后端全量 pytest 673 passed/1 skipped/68 xfailed/1 xpassed（唯一 failed=test_draft_service::test_cleanup_preserves_newest，draft 测试隔离预存 flaky 摆动 0-2，与本次改动不碰 draft 无关；本次新增 5 feedback_learner 全过 + 撤 standard-enforce 无回归，基线 668→673）；learn-feedback 端点端到端冒烟 skip_llm added=1 source=feedback_learned/enabled=False（待审）✓；前端各节点 tsc 0 错。**节点6 ✅ 完整 UI 闭环 playwright 验证全通过**：① 生成（点"生 成"+发送 → SSE 55s → 装配工艺表格，body 147→5944，装配/工序/力矩/扳手 FOUND，靠后端 HierarchicalContext 自动检索 material 1，前端 selectedMaterials 默认空不注入）② 改 cell（扳手→扭矩扳手，2 处 contentEditable cell，evaluate 设 textContent+blur 触发 onBlur→onChange 回写）③ 保存（SaveOutlined icon → handleSave PUT content 成功 + diff 采集）④ learn-feedback POST 自动触发（edits=2，section_id/row_key/col_key/old_value/new_value 结构完整）⑤ 后端 FeedbackLearner LLM 归纳规则入库（id=86362ba7 术语统一"力矩→扭矩"，source=feedback_learned/enabled=False 待审）⑥ ProfilePage 审查 UI 渲染真实候选规则（术语统一/反馈学习/候选规则/待审 markers FOUND）⑦ 启用（UI Switch → PATCH /principles/86362ba7 {"enabled":true} → assembly.json 持久化）⑧ 注入链路（writing_agent 1004 读 enabled 过滤 → 1009-1013 注入"## 画像强约束"，复用 profile-expand 现有机制全章节注入）。验证后清理：删注入测试规则 23d17a12、真实规则 86362ba7 恢复 enabled=False 待审、临时诊断/阶段脚本全清
- **完成**：standard-enforce（Step 4 标准强约束）—— 节点1✅ 标准条款注入 _do_template_fill system_msg（chapter_type→clause_type 映射 + SessionLocal + search_standard_clauses top_k 5，全章节注入）；节点2✅ review_service 加 _check_standards（LLM 判违规 + severity 映射 process/quality/safety=ERROR, format=WARNING）+ review async + review_agent await；节点3✅ pytest 668 passed（1 draft flaky 预存）。**注入/校验实测留 web/集成**。**数据库方案 Step 0-4 全部完成**。
- **完成**：profile-expand-and-relations（Step2 尾巴+Step3 画像）—— 节点1✅ triples 正则清洗（力矩数值禁连续小数点 + 标准 object 校验 + current_section 不返回泛词，documents/1 triples 10→5 全干净）；节点2✅ LLM 兜底校验 triples（_llm_validate_triples，fail-soft）；节点3✅ documents/1 重抽（assembly.json 5 干净 triples）；节点4✅ 画像注入移出 G25a gate 全章节（principles/triples 所有 _do_template_fill 章节）；节点5✅ 关联落库逻辑（extract_from_doc 产 relations + extract_and_save 落 StepMaterial + _parse_process_card content field_map），**documents/1 关联空因 G25a colspan-heavy content 提取（独立技术债，留后续）**；节点6✅ pytest（profile 9 passed + draft flaky 预存）。待用户开 Step 4（标准 review）。
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
