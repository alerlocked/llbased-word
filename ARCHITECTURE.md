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
- **Workflows**:full_edit[writing,proofread,review] / quick_edit[writing,proofread] / review_only[review] / proofread_only[proofread]。
- **Orchestrator 状态机**(`agents/orchestrator/state_machine.py`):IDLE → INTENT_RECOGNITION → INFO_ASSESSMENT / INFO_COLLECTION → ... → TASK_DECOMPOSITION → TASK_EXECUTION → RESULT_AGGREGATION → COMPLETION;特殊:DRAFT_ANALYSIS(初稿分析)/ PAUSED(等输入)/ ERROR(自恢复 IDLE)。

## 3. 生成流程(端到端)

- **入口**:`POST /api/agent/generate-stream`(`api/agent.py:853`)→ `orchestrator.process_intent` → SSE 事件(mode/progress/content/content_section/result/error)。
- **source-driven 直注(真主路径)**:`extract_*`(`services/hierarchical_context.py`)抽章节 → orchestrator 注入 `task["params"]` → writing_agent `preloaded_content` 直填。
  - extract 函数:assembly_steps(G25a)/ process_steps(G19a)/ process_card_steps(G22a)/ file_references(G5a)/ doc_catalog(G4a)/ assembly_overview。
- 倒推(`orchestrator._derive_strong_node`):G25a → G18a/G14a 等配套表;G18a 走 catalog enrich(`_enrich_names_from_catalog`,代号→名称 exact 查纠错位/填待补)。
- 无 source 章节 / chat → HierarchicalContext 兜底。

## 4. 上下文 + 检索

### HierarchicalContext(`services/hierarchical_context.py:105`,4 层)
- L0 元信息索引(`load_meta_index`)/ L1 表格索引(`load_table_index`)/ L2 表格 HTML(`extract_table_html`)/ L3 关键词检索(`global_keyword_search`,jieba 分词)。
- material filter:型号(model)/ 专业(specialty)穿透。

### 3 活检索路径
| 路径 | 角色 | 用途 |
|---|---|---|
| **source-driven 直注** | 主 | 有源章节(extract 直填,不走检索) |
| **HierarchicalContext** | 兜底 | 无源章节 / chat QA(关键词 + filter) |
| **material_catalog**(KnowledgeSearchService) | 结构化 | G18a enrich(`standard_code` exact 查 → name) |

### 废弃组件(2026-07-05 cleanup 删,**勿复活**)
向量(IndexingService / chromadb)/ 图谱(KnowledgeGraph)/ UnifiedRetrieval / SearchAgent。原因:工艺文件是结构化 QJ903 表格,向量召回引噪声;source-driven 直注 > 三层检索(见 `exp-retrieval-cleanup-and-dimensions`)。

## 5. 数据存储

- `backend/data/documents/{material_id}/`:`index.json`(元信息)/ `content.html`(MinerU 解析)/ `content.json`(结构化)/ `chapter_index.json` / `vlm/`。
- **DB 表**(`models/database.py`,SQLite):Material / MaterialCatalog / MaterialPage / Figure / ProcessStep / Standard / StandardClause / StepMaterial / StepTool。
  - 关联:ProcessStep ←StepMaterial/StepTool→ MaterialCatalog。
  - `MaterialCatalog.standard_code`:G18a catalog enrich exact 查键。
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
