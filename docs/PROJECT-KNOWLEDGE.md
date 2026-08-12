# 工艺文件辅助编辑系统 项目知识库

> 自动生成于 2026-07-14（codebase-documenter），如有冲突以项目 config 文件为准。
> 本文档是 win10 版移植 / 同步的**业务代码基准**——win10 须与本仓 `backend/app`+`frontend/src` 完全一致。

---

## 1. 项目概述

- **定位**：工艺意图 → 标准工艺术语 → 工艺文件生成。面向工艺师的 AI 辅助编辑系统。
- **Repo**：`alerlocked/llbased-word`（分支 `main`）
- **技术栈**：前端 React18+TS+Vite+AntD5+Tiptap2 / 后端 Python3.13+FastAPI+SQLAlchemy2.0+SQLite / AI LangChain+GLM-5 / PDF MinerU0.7.6(VLM) / 检索 HierarchicalContext(source-driven 直注)
- **当前状态**：35 Feature，29 完成(83%)；已跳过 PDM/Win7/麒麟兼容/WASM预览/E2E测试

## 2. 技术架构

### 2.1 三层架构

```
用户输入 → ProcessOrchestrator(主控) → 意图识别 → 路由 Functional Agent
  ├── WritingAgent    (文档写作, 4层上下文, 章节并行)
  ├── ReviewAgent     (合规+质量评审, Profile驱动)
  ├── ProofreadAgent  (术语标准化+数据纠正)
  └── (TerminologyAgent/ComplianceAgent 经工具实现)
         ↓
  Tools: terminology_mapper / compliance_checker / 搜索族 / HierarchicalContext
         ↓
  Services: llm_service / document_processor / vl_service / knowledge_extractor / learners
```

### 2.2 关键目录

```
backend/app/
  api/             20 个 API 模块(170+ 端点)
  agents/
    core/          Agent/Tool/Workflow 协议 + 注册表(registry.py)
    functional/    writing/review/proofread Agent(装饰器自动注册)
    orchestrator/  主控(orchestrator.py 3927行) + intent_recognizer + state_machine(15态63转换) + task_decomposer(8任务类型) + dialog_manager + info_assessor
    tools/         local/web/aliyun/bing 搜索 + terminology/compliance
  services/        30+ 服务(context/pdf/llm/material/learner/export)
  tools/           pdf_parser(双模式) + table_extractors + terminology + compliance
  models/          DB表(Material等) + Profile画像(ConditionGroup/Principle/Preference)
  repositories/    TaskMemory(json开发/sqlite生产, factory切换)
frontend/src/
  components/      editor(Tiptap) / AICreation(对话/素材/编辑面板) / MaterialLibrary(文件夹树)
  stores/          creationStore.ts(Zustand, 多项目+多会话+编辑历史)
  services/        apiClient(/api baseURL) / aiService / pdfService
  hooks/           useAIStream / useSelection / useSuggestions
```

### 2.3 核心模块

- **ProcessOrchestrator**（orchestrator.py）：意图识别(11种) → 任务分解(8类) → 状态机驱动 → Agent 路由 → 结果聚合。支持迭代修改(最多3轮)。
- **HierarchicalContext**：4层上下文(元信息/表格/按需表格/精确检索)，source-driven 直注（从源文档 HTML 提取，不靠 LLM 生成），G5a `extract_file_references()` 引用文件直填。
- **vl_service**：PDF 解析 VLM 后端切换（mineru/qwen/qwen_local）。
- **Profile 画像两层**：DB表（Material，含 model/specialty 检索维度）+ Profile（ConditionGroup 知识 / Principle 合规硬规则 / Preference 偏好软规则）。

## 3. 网络端口与部署

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8000 | FastAPI + uvicorn |
| 前端 dev | 3000 | Vite（生产由后端单端口 serve，见 win10） |
| LLM(本地部署) | 1028 | MindIE Qwen3-30B-A3B（.env 配 `DASHSCOPE_BASE_URL_COMPLEX`） |
| VLM(本地部署) | 1040 | mineru http-client 打 MindIE / vllm-ascend |

**本地运行**：
```bash
cd backend && pip install -r requirements.txt && python main.py   # :8000
cd frontend && npm install && npm run dev                          # :3000
```

**关键配置**（config.py）：
- `VL_SERVICE_BACKEND`：`mineru`(默认,本地GPU) / `qwen`(云端DashScope) / `qwen_local`(MindIE)
- `MINERU_BACKEND`：transformers / http-client（部署机打服务器:1040）
- `MODEL_TIER_SIMPLE/COMPLEX`：qwen-turbo / qwen-plus（本地 qwen3-30b-a3b）
- `DASHSCOPE_BASE_URL_COMPLEX`：本地部署指 `http://<server>:1028/v1`

## 4. API 参考（20 模块 170+ 端点）

| 模块 | prefix | 核心端点 |
|------|--------|----------|
| agent | /api/agent | start-conversation / reply-question-stream / select-plan / generate-stream / chat |
| assistant | /api/assistant | intent / suggestions / generate-stream / quick-actions-stream / contextual-ask |
| creation | /api/creation | projects CRUD / materials(项目+全局) / documents(上传PDF) / images / batch-upload / generate-index |
| document | /api/documents | 列表 / tables / markdown / context / summary |
| draft | /api/drafts | upload / 版本 / rollback / diff / export(pdf/word) |
| profile | /api/profile | 画像 CRUD / learn(文档/反馈) / knowledge / principles / preferences |
| pdf_status | /api/pdf | status / tasks(CRUD/batch) / watcher(start/stop/paths) |
| process_documents | /api/process-documents | 列表 / extracted / tables / export-csv / parser-config |
| task | /api/tasks | 任务 CRUD / messages / decisions / proofread / review |
| node_documents | /api/node-documents | 会话节点文档 / latest / search(LTM) |
| context | /api/context | template / examples / build |
| deepseek | /api/deepseek | chat / generate-document / align-terminology / check-compliance |
| export | /api/export | word / content-pdf / content-word |
| materials | /api/materials | summary / pages / 列表（文件系统，不依赖DB） |
| process | /api/process | clean-text / extract-entities |
| web_image | /api/web-image | search / evaluate / list |
| annotation | /api/creation(annotations) | 注释 CRUD |

> `knowledge.py` 已弃用，未在 main.py 注册。

## 5. 数据流（主链：上传 PDF → 解析 → 生成 → 导出）

```
1. 上传 PDF（creation/projects/{id}/documents 或 pdf/tasks）
   └─ material_classifier.infer_model_specialty → Material 表(model/specialty 维度)
2. PDF 队列（pdf_queue_manager.add_task，哈希去重+优先级）
   └─ document_processor.process_document:
      PDF→图片(zoom3.0) → vl_service(mineru batch OCR) → generate_document_html
      → knowledge_extractor 落库(物料/工序/标准, QJ903 表格结构化)
3. 生成工艺文件
   └─ hierarchical_context.build_context(L0-L4 + G5a extract_file_references 直填)
      → WritingAgent(llm_service complex tier, 章节并行) → Proofread(术语) → Review(合规)
4. 学习：feedback_learner(修改→规则) / document_profile_learner(文档→三元组) / preference_learner
5. 导出：word_export / csv_export（docx2pdf 中文路径须 staging ASCII temp dir）
```

**数据存储**：文档按 `material_id` 组织（跨项目共享）。`backend/data/documents/{material_id}/`（index.json/content.html/content.json）+ uploads/ + standards_parsed/(QJ903)。SQLite（craftdoc.db）。

## 6. 使用说明

- **环境**：Python 3.13 + Node；`.env` 配 LLM/VLM 后端（开发云端 / 部署内网服务器）
- **PDF 解析后端选择**：开发机有 GPU → mineru(transformers/cuda)；无 GPU → mineru 本地 CPU(慢) 或部署 http-client(打服务器:1040)；云端 → qwen(qwen-vl-max)
- **win10 部署**：见 win10 版 `DEPLOY.md`（便携包 + 单端口 + 内网瘦客户端）

## 7. 开发指南

- **新增 Agent**：functional/ 下写 + `@AgentRegistry.register("name")`，discover_agents 自动扫
- **新增工具**：tools/ 下写 + ToolRegistry 装饰器
- **新增 workflow**：core/registry.py 注册（如 full_edit=writing→proofread→review）
- **测试**：`pytest`（当前 685 passed）；测试代码进 tests/，产物进 .test-runs/
- **win10 同步**：主仓更新后覆盖 win10 的 backend/app+frontend/src，保留 win10 main.py(SPA)+.env（见 win10 exp-win10-main-mirror-principle）

---

*本文档由 codebase-documenter 生成，仅供 Claude/skill 参考。与 config 冲突时以 config 为准。*
