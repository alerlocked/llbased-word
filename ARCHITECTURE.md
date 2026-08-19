# ARCHITECTURE · 工艺文件辅助编辑系统(localknowledgebase-word)

> **单一架构源**。本文是项目架构的唯一事实源,反映代码真实状态。CLAUDE.md / DEV-LOG 不重复架构(只指针)。
> **维护规则**:涉及架构改动(agents / 检索 / 数据 / 生成流程),lead 收尾必须更新本文;DEV-LOG「当前状态」记架构变更点(见 CLAUDE.md 文档规范)。
> 更新:2026-07-21(arch-catalog-index,据代码实测)。

## 1. 总览

工艺意图 → 标准工艺术语 → 工艺文件生成。多层 Agent:用户输入 → Orchestrator(意图识别 + 状态机)→ 功能 Agent → SSE 输出。检索以 **source-driven 直注**(extract 抽章节直填)为主,HierarchicalContext 关键词兜底,material_catalog 结构化查(G18a)。

```
用户输入 → POST /api/agent/generate-stream
  → Orchestrator.process_intent(意图识别 + 状态机)
  → 功能 Agent(writing/review/proofread)
  → SSE(mode/progress/content/result/error)
前端:AIChatPanel → SSE → ProcessTableEditor / ProcessContentView / Tiptap
```

## 2. Agent 系统

- **功能 Agent**(`agents/core/registry.py` 注册):`writing`(撰写)/ `review`(审查)/ `proofread`(校对)。
  - ⚠️ **Search Agent 已删**(2026-07-05 cleanup);Compliance 是 review 的 tool(`compliance_checker`),非独立 Agent。
- **Tool**:`compliance_checker`(合规)/ `terminology_mapper`(术语)。
- **任务调度**:`_dispatch_to_sub_agent`(orchestrator.py)按 task_type 映射到单 agent(writing/review/proofread);无 workflow 编排链路(`_select_workflow`/`execute_workflow` 为死代码,2026-07-30 清理)。
- **Orchestrator 状态机**(`agents/orchestrator/state_machine.py`):IDLE → INTENT_RECOGNITION → INFO_ASSESSMENT / INFO_COLLECTION → ... → TASK_DECOMPOSITION → TASK_EXECUTION → RESULT_AGGREGATION → COMPLETION;特殊:DRAFT_ANALYSIS(初稿分析)/ PAUSED(等输入)/ ERROR(自恢复 IDLE)。

### 意图准入 + 审查流(2026-08-17 review-pipeline 加)
- **问句闸门**(intent_recognizer `_QUESTION_FORM`):问句形式("…还需要补充吗/有什么问题吗")永不触发 draft_complete 复合 boost——补全只认命令式。23:18 事故根因(问句+补充+文件→0.85 覆盖→重写全文件)。
- **准入守卫**(`orchestrator._gate_draft_complete`):**生成/补齐只从按钮(generation_mode∈generate/fill)触发**;对话文本识别出的 draft_complete 无 generation_mode → state="gated" 澄清回复,绝不执行。按钮路径行为不变。
- **四对照审查执行器**(`services/review_pipeline.py`):review_document 意图 → ①模板章节差集(机器,模板是缺章唯一裁判) ②DB 材料有据(MaterialCatalog 查,info 级) ③内容质量(空格/待补/warnings 扫描) ④需求覆盖(唯一 LLM,simple 档,只能引用①②③事实清单,禁通识)。回复纯聊天文本(SSE content),不碰编辑器。无 structured_results 时回退 state.last_output 快照。
- **修改意图安全兜底**:edit_document 从对话进来(同事执行单元未合入)→"功能建设中"回复,不改文件。
- **意图路由**(agent.py):gated / review_document / edit_document 三分支在 draft_complete 主分支之前拦截。

## 3. 生成流程(端到端)

- **入口**:`POST /api/agent/generate-stream`(`api/agent.py:853`)→ `orchestrator.process_intent` → SSE 事件(mode/progress/content/content_section/result/error)。
- **source-driven 直注(真主路径)**:`extract_*`(`services/hierarchical_context.py`)抽章节 → orchestrator 注入 `task["params"]` → writing_agent `preloaded_content` 直填。
  - extract 函数:assembly_steps(G25a)/ process_steps(G19a)/ process_card_steps(G22a)/ file_references(G5a)/ doc_catalog(G4a)/ assembly_overview。
    - **G25a 引子合并**(2026-08-19 g25a-step-prefix-fixes):`extract_assembly_steps` 后处理——工序开头连续无 `N.M` 编号的引子行(含折行断句)并入首个带编号工步 content 头(非空 material/instruments `、` 合并),不独立成步(否则 LLM 按 i.N 顺排,引子占 8.1、真内容从 8.3 起);整道工序全无编号保持现状。
    - **G19a 骨架噪声过滤**(同上):`extract_process_steps` 过滤签名区/页脚格(`阶段标记/更改标记` + `^(?:共\s*\d+\s*页|第\s*\d+\s*页)$` 锚定全匹配,防误杀含「第1页」字样的真工序名)。
  - **G25a 相辅相成**(2026-07-24 g25a-method-aux-bind):gen_one 套用素材(`extract_reference_methods`)+辅料标准(L3.5 KG)→ LLM 同次产出工艺方法+辅料+参数 → aux 覆盖辅料列(绑定一致,substeps 直填退 fallback)。详见 `exp-g25a-cohesive-model`。
  - **G25a per-row 并行 + content 编号后处理**(2026-07-26 g25a-step-numbering):`_generate_g25a_per_row_parallel`(`writing_agent.py`)每工序一个 LLM call(Semaphore(4) 并发,避 max_tokens 截断 + 聚焦单工序质量);content slot 返回前 `re.sub` 行首 `N.M` 编号第一段强制 = 工序号 i(防 LLM 照抄原文编号——工序9 显 1.1 → 9.1;嵌套编号/无编号续行不动)。教训:LLM 结构化生成的编号/格式约束光靠 prompt 拉不住,要后处理兜底。详见 `exp-g25a-step-numbering`。
    - **工序名程序化前置**(2026-08-19 g25a-step-prefix-fixes):编号后处理之后 `_g25a_prefix_content` 把 `f"{工序名}：\n"`(skel[i-1] G19a 真工序名)拼到 content 头,不问 LLM(prompt「可点题」被跳过的根治);strip 串首同名前缀防重复;`_fallback_slots` 降级路径同拼。
- 倒推(`orchestrator._derive_strong_node`):G25a → G18a/G14a 等配套表;G18a 走 catalog enrich(`_enrich_names_from_catalog`,代号→名称 exact 查纠错位/填待补)。
- 无 source 章节 / chat → HierarchicalContext 兜底。

## 4. 上下文 + 检索

### 项目工作状态 + 项目级记忆(2026-08-16 session-continuity 加)
- **ProjectStateService**(`services/project_state_service.py`):项目级滚动工作状态(session 接续)。存储 `data/project_state/{project_id}.json`(7 字段:current_task ≤200 字/focus_chapters ≤5/recent_intents ≤5/user_preferences/last_session_id/updated_at/project_id),原子写(tmp+os.replace,threading.Lock)。**注入链**:`_build_orchestrator_context`(agent.py)加载渲染块 → ① fallback LLM system_msg(`_build_llm_messages` project_state_block 参数)② orchestrator `_dispatch_to_sub_agent` 把块挂 agent_task → writing_agent system_msg 追加(两处组装点:通用 + `_do_template_fill`)。**写入**:4 个产出点旁 `_update_project_state`(提取 G25a 类章节码 + 意图 + 偏好信号词"以后都/统一"等)。多用户将来加路径层 `{user_id}/{project_id}/`(工厂函数一处改)。
- **memory 按项目分域**:`data/memory/projects/{project_id}/`(`get_project_memory_service` 工厂,惰性缓存)。`build_context`/`_load_filtered_memory` 加 `project_id` 可选 kwarg——项目目录优先,空则回退全局目录(存量全局文件不迁移)。`_save_memory` 带 project_id 时路由项目级。

### LLM 韧性层(2026-08-16 local-resilience 加)
- **错误分类**(`services/llm_errors.py`):`LLMErrorClass` 7 类(timeout/connection_refused/context_overflow/empty_reply/json_parse_fail/rate_limit/unknown)+ `classify_exception`/`classify_error_text` + `USER_FACING_MESSAGES` 中文可读映射 + `should_retry` + `trim_messages_for_overflow`(只裁最长 user 消息,system 不动)。
- **重试包装**(`llm_service._generate_with_retry`):`generate_with_messages`/`generate_text` 1+2 次重试指数退避;context_overflow 裁剪一次后仍在预算内重试;empty_reply 同消息重试;错误 dict 增量加 `error_class` 键(原 4 键契约不动);流式接口错误也分类+可读化。structlog(`llm_call_retry`/`llm_call_failed`)。

### G25a per-row 韧性 + 完成度上报(2026-08-16 加)
- `_generate_g25a_per_row_parallel` `gen_one`:LLM error/JSON parse fail 原地重试 2 次(0.5/1.0s 退避,`g25a_per_step_retry` 日志带分类)。
- gather 后**完成度核对**:`rows_covered` vs n,缺口 `g25a_completeness_gaps` 日志 + 返回 4 元组加 `row_gaps`;`_do_template_fill` 返回 dict 增量加 `warnings` 键(沿 structured_results 管道零改动穿透到 agent.py)→ SSE `{'type':'warning','message':'[G25a] 工序 5…'}` 事件(content/result 之前 yield)→ 前端 AIChatPanel `warning` 分支渲染 `⚠`。治"工序四有/五空/六有"静默交付(违反 VISION 可靠验收的漏网点)。

### HierarchicalContext(`services/hierarchical_context.py:105`,4 层)
- L0 元信息索引(`load_meta_index`)/ L1 表格索引(`load_table_index`)/ L2 表格 HTML(`extract_table_html`)/ L3 关键词检索(`global_keyword_search`,jieba 分词)/ **L3.5 KG**(`_search_knowledge_graph`,全局 craft_kg 辅料-标准-参数图谱,2026-07-24 加)。
- material filter:型号(model)/ 专业(specialty)穿透。

### 3 活检索路径
| 路径 | 角色 | 用途 |
|---|---|---|
| **source-driven 直注** | 主 | 有源章节(extract 直填,不走检索) |
| **HierarchicalContext** | 兜底 | 无源章节 / chat QA(关键词 + filter) |
| **material_catalog**(KnowledgeSearchService) | 结构化 | G18a enrich(`standard_code` exact 查 → name) |

### 废弃组件(2026-07-05 cleanup 删,**勿复活**)
向量(IndexingService / chromadb)/ UnifiedRetrieval / SearchAgent。原因:工艺文件是结构化 QJ903 表格,向量召回引噪声;source-driven 直注 > 三层检索(见 `exp-retrieval-cleanup-and-dimensions`)。
> ⚠️ **图谱区分**:2026-07-05 删的是**老 KG 死壳**(0 调用);2026-07-24 g25a-method-aux-bind 重新上**全局 craft_kg**(`services/knowledge_graph.py`,networkx,文件持久化 `data/knowledge_graph.json`,L3.5 层 + G25a 相辅相成用)——这是**活的**,勿与老死壳混淆(见 `exp-g25a-cohesive-model`)。

## 5. 数据存储

- `backend/data/documents/{material_id}/`:`index.json`(元信息)/ `content.html`(MinerU 解析)/ `content.json`(结构化)/ `chapter_index.json` / `vlm/`。
- `data/project_state/{project_id}.json`(2026-08-16):项目滚动工作状态(见 §4)。`data/memory/projects/{project_id}/`(2026-08-16):项目级会话记忆(回退全局 `data/memory/`)。project_state 含 `last_output` 快照(2026-08-17:章节摘要+警告计数,跨会话指代"刚才生成的那篇"的实体)。
- **DB 表**(`models/database.py`,SQLite):Material / MaterialCatalog / MaterialPage / Figure / ProcessStep / Standard / StandardClause / StepMaterial / StepTool。
  - 关联:ProcessStep ←StepMaterial/StepTool→ MaterialCatalog。
  - `MaterialCatalog.standard_code`:G18a catalog enrich exact 查键。
  - `MaterialCatalog.tech_params`(JSON,2026-07-24):辅料技术参数 `[{param_name,value,unit,standard_source}]`,in-context 先行(2a),结构化下沉(2b)。
- **全局 craft KG**(`data/knowledge_graph.json`,networkx,2026-07-24):跨 profile 工艺知识图谱(辅料-标准-参数-工序),启动加载(`init_craft_kg`),供 L3.5 层检索。**灌数据链路**(2026-07-25 craft-kg-from-learn):「学习为画像」(`POST /api/profile/{domain}/learn` 单文件 / `learn-file` / `learn-batch` 文件夹批量 SSE)→ `DocumentProfileLearner.learn_from_content` 产 triples → `_feed_craft_kg`(`build_from_triples`→`craft_kg.merge_from` 累加幂等,`_safe_id` 跨文件同名工序去重→`save_craft_kg` per-file 增量持久化);learn-batch 端点预读 content(gen 不持 DB Session)+ SSE per-file 进度。详见 `exp-g25a-cohesive-model` / `exp-craft-kg-feed-from-learn`。
- `data/profiles/`(assembly/welding/coating.json 画像)/ `tasks/`(任务记忆)/ `memory/`(对话记忆)。

## 6. 前端(`frontend/src`)

- React 18 + TypeScript + Vite + Ant Design 5 + Tiptap 2。
- Zustand `creationStore`(`persist` localStorage `creation-storage-v2`):editorContent / editorTemplateData / projects / chatHistory。
- AIChatPanel → generate-stream SSE → 渲染:`ProcessTableEditor`(表格编辑)/ `ProcessContentView`(卡片预览,markdown parser)/ Tiptap(markdown)。

## 7. 运行

- 后端:Python 3.13 + FastAPI,`backend/main.py`(:8000)。LLM = Qwen(`DASHSCOPE_BASE_URL_COMPLEX`,云端 / 本地千问 .env 切换)。
- 前端:Vite dev(:3000)/ 构建后后端单端口 serve。
- PDF 解析:MinerU(VLM,云端 / 内网服务器 1040)。
- 部署:win10 瘦客户端 + 内网服务器(LLM:1028 / VLM:1040),见 `DEPLOY.md`(win10 版)。
