# 工艺文件辅助编辑系统

> 基于AI的工艺文件智能编辑与辅助系统

## 快速开始

### 环境要求
- Python 3.13+
- Node.js 18+
- SQLite

### 启动后端
```bash
cd backend
pip install -r requirements.txt
python main.py
```
后端运行在 http://127.0.0.1:8000

### 启动前端
```bash
cd frontend
npm install
npm run dev
```
前端运行在 http://127.0.0.1:3000，自动代理 API 到后端。

### 初始化数据库
```bash
cd backend
python init_db.py
```

---

## 功能说明

### 1. 文档编辑器
基于 Tiptap 的富文本编辑器，支持工艺文件的在线编辑。

- 打开首页 → 左侧为素材库/文档列表，右侧为编辑区
- 支持富文本格式、图片插入、表格
- 自动保存

### 2. 素材库管理
管理工艺文件所需的素材资源。

- 上传 PDF/图片等素材文件
- 素材分类、检索
- API: `GET /api/materials`

### 3. PDF 上传与解析
上传 PDF 文件并自动解析为可编辑内容。

- 上传 PDF → 进入解析队列 → 解析完成显示在编辑器中
- API: `POST /api/documents`（上传）、`GET /api/documents/{id}`（查看）
- 解析状态查询: `GET /api/pdf-status/{task_id}`

### 4. AI 辅助写作
集成 LLM（GLM-5）提供智能写作辅助。

- **继续写作**：根据上下文自动续写
- **生成摘要**：对当前内容生成摘要
- **智能对话**：通过对话式交互修改文档
- API: `POST /api/assistant/*`

### 5. AI 创作模式
多 Agent 协作的文档生成模式。

- Agent 协作视图：多个 Agent 共同完成文档创作
- 对话面板：与 Agent 交互
- 素材报告视图：基于素材自动生成报告

### 6. 上下文感知系统
HierarchicalContext 系统提供文档上下文管理。

- 多层级上下文：文档级 → 段落级 → 句子级
- API: `GET /api/context/{document_id}`

### 7. 草稿管理
保存和管理工作草稿。

- API: `GET /api/drafts`、`POST /api/drafts`、`PUT /api/drafts/{id}`

### 8. 文档导出
将编辑完成的文档导出。

- API: `POST /api/export`

---

## 技术架构

```
frontend/          React + TypeScript + Vite
├── src/
│   ├── components/    UI 组件
│   │   ├── editor/       编辑器组件
│   │   ├── AICreation/   AI 创作组件
│   │   ├── MaterialLibrary/  素材库组件
│   │   ├── Upload/       上传组件
│   │   └── ...
│   ├── agents/        Agent 逻辑
│   ├── services/      API 服务
│   ├── stores/        状态管理
│   └── contexts/      React Context

backend/           FastAPI + Python
├── app/
│   ├── api/          API 路由（19 个模块）
│   ├── agents/       AI Agent 系统
│   │   ├── core/        核心协议与注册
│   │   ├── functional/  功能 Agent（写作/审阅/校对）
│   │   ├── orchestrator/ 编排器（对话管理/意图识别/状态机）
│   │   └── search/      搜索 Agent
│   ├── models/       数据模型
│   ├── services/     业务逻辑
│   ├── repositories/ 数据访问层
│   └── tasks/        异步任务
└── main.py           入口
```

---

## 开发进度

### v0.4 — 2026-05-30（当前）

**核心流程：上传初稿 → AI 分析缺失章节 → 知识库检索 → 并行生成 → 逐章 review**

- 初稿分析报告：对比知识库文档，自动列出缺失/不完整章节
- 章节并行生成：每个章节独立调用 WritingAgent，注入对应知识库原文
- 逐章 review-retry：ReviewAgent 逐章检查，不合格自动重试
- 工艺过程卡结构化渲染
- 输出质量门控（单元测试 + E2E 断言）
- 大章节拆分（>5 页按子章节生成，避免 token 溢出）
- 签名字段自动剥离

### v0.3 — 2026-05-25

- 章节索引 + 章节级内容检索（HierarchicalContext 4 层）
- 初稿分析报告生成
- 多轮生成（multi-pass generation）

### v0.2 — 2026-05-24

- AI 创作面板 UI
- auto-confirm 流程（草稿完善自动确认执行）
- 多 Agent 协作视图
- 进度文字提示

### v0.1 — 2026-04

- 基础编辑器（Tiptap）
- PDF 上传解析（MinerU-VLM）
- 素材库管理
- 术语标准化 / 合规检查 Agent
- 对话式 AI 辅助

---

## 项目结构规范

- 路径边界: `.project-meta/ai-rules.yaml`
- 环境锁定: `.project-meta/env-lock.yaml`
- PIV 文件: `PRPs/`
- Sprint Contract: `contracts/`
- 验证报告: `reports/`
- 测试截图: `reports/screenshots/`

---

*最后更新: 2026-05-31*
