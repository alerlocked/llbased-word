# TODO · localknowledgebase-word

> 项目待办清单（债务 + 问题）。完成一条标 ✅ 或移到底部「已归档」。
> 来源：2026-07-19 gen-test-fixes 收尾梳理 + exp/DEV-LOG open items。
> 优先级：**挡交付 > 系统完善 > 治理小尾**。PMF 阶段服从商业（基本盘保交付，不过度工程）。

---

## P0 · 挡交付质量（优先）

### 1. ✅ G5a/G12a/G14a extract 漏抽 → G12a/G14a 修（v2），G5a 不修（OK）
- **G12a/G14a ✅ 修**（extract-fields-fix v2，commit `c06b036`）：双层列头 v2 支持（A material alias + B/B+ 去空格/长优先 + C 双层合并），material_desc 抽真材料、quota 无"净重"/"单套"噪声。真实 fixture 单测 + pytest 670 不回归
- **G5a ✅ 不修**：file_references 直填覆盖（ref_name=1 是兜底日志残留）
- **留（可选增强）**：G12a `unit=0`（根因 4 网格列轴错位 unit@15 vs 数据@14，上游 `_expand_table_grid` colspan 起点）— 影响小，等 unit 仍空再上
- 关联：[[exp-dual-header-extract]] / commit `c06b036`

### 2. ✅ G4a 工艺文件目录 extract（g4a-source-extract）
- **完成**（PLAN f72c2fb，commit 3f3df0a/0142020）：照 G5a 三件套 `extract_doc_catalog`（非空顺序法抗 colspan 漂移 + 编号/代号 header 锚点）+ orchestrator 注入 + writing_agent 消费 8 列直填 + LIST_CHAPTERS 删 G4a。真实 documents/1 抠 10 行全对（doc_name=章节名/零部组件=产品本身/页数真实）+ pytest 676 不回归。端到端留 web/sync 后验。
- 关联：[[exp-g4a-source-extract]] / commit 0142020

### 3. ✅ G10a/G14a/G12a 前后端 column-key 不一致（已对齐，方案A）
- **已修**（PLAN cb7aa10，主仓 `f8fc1a6` + win10 `d05aa1c`，2026-07-21）：backend template 对齐 frontend 名（G10a `for_code/name`、G14a `comp_code/name`、G12a 加 `blank_yield`）+ `_CODE_LIKE_KEYS` 保留 `component_code`（G1a/G4a 隔离）。guard `validate()` 0 mismatch + pytest 676 passed。前端 layout 0 改。guard `KNOWN_DIFFS` 死白名单留 harmless（清走 NTM_MAINT）。
- 原现状：契约 guard 暴露 KNOWN_DIFFS（G10a `for_component_*`↔`for_*`、G14a `component_*`↔`comp_*`、G12a 前端多 `blank_yield`），guard 白名单兜底
- 建议：单独排期对齐（影响 structured 提取 + 前端取值 + 已有数据）
- 关联：[[exp-generation-debugging]] §1.7 / `scripts/hooks/guard-column-align.py` KNOWN_DIFFS

---

## P1 · 系统完善（场景驱动 / 上线前）

### 3d. ✅ 画像学习 domain 断链修复（2026-08-22，feature/workspace-empty-gate `a60dfa9`）
- **完成**：`GET /projects/{id}/materials` documents 补传 `specialty`（上传时 LLM 推断、库里已有但接口漏传）→ 前端 `file.domain` 接上 → "学习为画像"（单文件+文件夹批量）按素材专业进对应域库，不再一律写死装配库。+1 回归测试（字段存在性）。生成侧本就按 domain 选库（`orchestrator.py:353`），至此"上传→自动分流入库→按模板点亮对应域"整链通
- **留**：`WorkspacePage:340` learn-feedback（保存时 diff 反馈学习）仍写死 assembly——打通需 CreationProject 加项目级专业字段，接入第二个专业时一并做

### 3c. ✅ G25a 工序名称前置直拼 + 工序8无编号引子提取修复（2026-08-18 用户实测报告，2026-08-19 修，PLAN `c5da04b` + N6 重 seal `39a0c2e`）
- **完成**（feature/arch-g25a-step-prefix-fixes，PR #64，N1 `e5fb769` + N2 `f6c5d3d` + N6 `ec62740`）：① `_g25a_prefix_content` 程序化前置 `f"{工序名}：\n"`（skel[i-1]，编号后处理之后 + `_fallback_slots` 降级路径 + strip 防重复）② `extract_assembly_steps` 后处理引子合并（工序开头连续无 `N.M` 行并入首带编号工步，全无编号保持现状）③ G19a 骨架过滤 `阶段标记/更改标记/共N页/第N页` ④（PR 审查 warn 用户拍板本 PR 修）画像物料 triple 改**全段提取**（`document_profile_learner` 材料格 `、/,/，` 逐段清洗入库，不再只取首段——预存缺陷一并治好；**用户原则：画像提取针对实际内容，不按行位置取首段**）。新增单测 17 个（引子合并 4 + 噪声 2 + 前缀 7 + 物料全段 4）；全量 **918 passed 0 failed**（顺带修复 main 存量失败 `test_prompt_requires_step_name_prefix`——d6b2aa3 撤前缀文案后测试没跟上，实测 HEAD 干净状态确失败）；**真实链路冒烟过**（documents/1 + 云端 LLM：骨架 10 步零噪声、工序6/8 引子已并入 6.1/8.1、content 以「装前准备：\n1.1 …」开头，产物 `.test-runs/g25a-step-prefix-fixes/smoke-real-llm.log`）
- **留**：web 端整卡重生成验收留用户部署环境（生成效果仍差再回查 6cbaf30 F2 A/B）；画像清洗 spec_cut `[A-Za-z0-9/]` 不切 `φ` 希腊字母（预存行为，要支持属管线增强另立项）
- 关联: g25a-step-numbering `d6b2aa3` / exp-g25a-step-numbering

### 3b. edit_local 对话式局部修改（dialog-task-pipeline 第5块，2026-08-12 开）
- **方向已定**（2026-08-11 PlanMode 探索 + 用户拍）：定位=**框选 + 自然语言都要**；改的对象=**表格 cell + 段落**（上传工艺文件改某段，不止 cell）；明天拆小块 lead 循环，从"框选 cell 改"起步（定位准、复用 unify 选区思路）
- 现状：前端 `editorTemplateData` 有 cell 坐标(chapter_code,rowIndex,columnKey)+更新路径现成，但**表格无 cell/段落选区机制**(只 hover，文本段选区 unify 已有)；后端 **`_do_edit` 整段重生成**(不能改单值)/edit_document 链路错配(跑成 proofread+review)/**无反向 cell 定位**/SSE 只全量更新
- 明天要建：表格 cell/段落框选选区 + 自然语言定位(NER+映射) + edit 执行单元(改单值/改段) + cell_update SSE 局部回传
- **意图路由两病灶（2026-08-18 实测"帮我把引用文件目录完善"记录,随 edit_local 一起修,现在不动——#63 接入后 edit 链路能识别局部修改句式,自然不再误触发生成）**：
  1. draft_complete 复合 boost（`intent_recognizer.py:83` 关键词 `补全|完善|补充` + 文档词 → 无条件 0.85）**覆盖 LLM 语义结果**——点状修改句式（"把X完善"）与整份补全分不开，LLM 大概率判对的 edit_document 被关键词劫持。修法：boost 前先跑 LLM 判 edit_document 优先短路
  2. gate 兜底文案（`orchestrator.py:543` 硬编码长文案）为"想生成被拦"设计,套在"想局部修改"头上文不对题。修法：砍成一句 + 识别为修改意图时改走 `agent.py:1002` edit 兜底（"修改功能建设中,用编辑器框选"）
- **按钮收敛完成（2026-08-18,commit `0be2706`）**:右下角 4 按钮收敛为 1——审/校按钮删（对话路由已覆盖:审查/校对句式→review_document 0.85 实测）;生成并入补齐（fill 无初稿后端自动转全量,零后端改动）。顺带修了既有 bug:global.css `.ant-btn-default !important` 杀掉 inline 高亮背景,加 `mode-btn-active` class 恢复。
- 关联：ALIGN-dialog-task-pipeline D4 / [[exp-dialog-task-pipeline]] 待办 / VISION 交互升级线

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

### 7a. triples-spec-param 后续（N2 单测 / 节点类型 / 规格扩展 / KG匹配度）
- 现状：triples-spec-param N1+N3 完成（commit 3c0c2a3，规格作 subject + 同句边界，规格-参数关联进 graph）。**2026-07-26 端到端实证**：M4 螺柱/T2D30070→力矩1.9 抽到 ✅，但 **M5 螺柱3.6N·m 漏抽**（content.html "螺柱 M5 8 A2-70" 拆散表述 pattern 覆盖不到）+ **M4 节点 type=process_step**（build_from_triples 全标 process_step，该按 subject 判规格/材料）+ **craft_kg 节点 label vs G25a 工序名 keyword 匹配弱**（_search_knowledge_graph seed_ids 模拟=[]，has_aux=true 主要靠 DB knowledge_search，KG 贡献小）。留：① N2 正式单测；② build_from_triples 节点类型（规格标 [规格]/[材料] 非 [工序]）；③ 规格识别扩展（M\d+×\d+ 拆散/GB-T 标准号作 subject）+ LLM 抽；④ craft_kg 匹配改进（label 加规格别名 / keyword 扩同义词）让 KG 真贡献 aux。
- 建议：② 顺手（type 标错误导下游）+ ③④ 按需（KG 检索效果）
- 关联：ALIGN-triples-spec-param / commit 3c0c2a3 / [[exp-craft-kg-feed-from-learn]] / DEV-LOG 端到端验证 2026-07-26

---

## P2 · 治理 / 流程 / 小尾巴（不单独立项）

### 9. diagnose 脚本被清
- 现状：`diagnose_all_chapters.py` / `diagnose_g25a.py`（exp 推荐诊断工具）已不在 backend/，本次 #1 靠 python -c + Read 临时顶
- 建议：要么恢复脚本进 `scripts/`，要么把诊断手法固化进 exp
- 关联：[[exp-generation-debugging]] §1.9/§2

### 10. profile 注入无日志
- 现状：`writing_agent.py:1012` 拼 `## 画像强约束` 进 system_msg 不打 logger，日志无法确认是否生效
- 建议：顺手加一行 log（做 #1 extract lead 时顺带）

### 12. ✅ 工作区垃圾文件（2026-08-18 对账发现，2026-08-19 根治归档）
- **exports 垃圾根治**（`361a3bb`）：根因 = `test_csv_export.py` 的 `test_output_dir` fixture 把输出锚进 git 跟踪的 `tests/fixtures/exports/`，每次全量回归重新生成 batch_export 垃圾 + 脏改跟踪的 metadata.json（无任何读方，grep 核实）。修 = fixture 改 pytest `tmp_path` + `git rm -r` 全部泄漏输出（−402 行，含 0622/0705 历史泄漏）+ .gitignore 补路径兜底。复跑 7 passed 零再生
- `backend/data/project_state/` .gitignore 已盖（`9f1bd1d`）；`___TEMP_OUT___` / `backend/backend/` 2026-08-19 复核已不存在（记录过时）
- 关联：project-audit 2026-08-18 / TODO 3c 收尾对账

---

## 已归档 / 已完成
- 2026-08-18 #8 git 分叉 —— **旧账，已核实归档**：2026-08-13 治理 force push 对齐后零分叉（project-audit 实测 main vs origin/main = 0/0），后续无复发
- 2026-08-18 #11 VISION.md 未建 —— **过时信息，已核实归档**：文件 2026-07 已建；本日补「可改」验收轴 + 交互升级线（PR #63 方向，commit `1fd409e`）
- 2026-07-25 G25a 装配卡检验项堆最后 —— 撤销，用户确认实际无此问题（代码层穿插本就对：`_expand_inspection_rows` 每步后插检验行 + 前端 `ProcessCard`/`processCardParser.ts:102` 归当前 step；原为 2026-07-21 便携包 v0.2 测试定位的疑点）
- 2026-07-19 gen-test-fixes：#2 /health 404、#3 SQL echo、#4 事件循环阻塞 67s —— 均已修（commit `bf954f2`）

---
*更新规则：完成一条 → 标 ✅ 或移「已归档」；新债务追加到对应优先级组。*
