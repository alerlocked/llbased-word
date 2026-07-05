# 工艺文件辅助编辑系统

> 工艺意图 → 标准工艺术语 → 工艺文件生成

## Repo

- GitHub: `alerlocked/llbased-word`
- Project Board: https://github.com/users/alerlocked/projects/1
- 当前分支: `feature/v1-cleanup`

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + Tiptap 2 |
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + SQLite |
| AI | LangChain + GLM-5 |
| PDF | MinerU 0.7.6 (VLM 高精度解析) |
| 检索 | HierarchicalContext（关键词 + 章节结构，source-driven 直注）+ Material model/specialty 维度穿透 |

## 本地运行

```bash
# 后端
cd backend
pip install -r requirements.txt
python main.py              # http://127.0.0.1:8000

# 前端
cd frontend
npm install
npm run dev                 # http://127.0.0.1:3000
```

## 架构

### Agent 系统

```
用户输入 → Orchestrator → 意图识别 → 路由到 Agent
  ├── WritingAgent    (文档写作，带 4 层上下文)
  ├── ReviewAgent     (合规检查 + 质量评审)
  ├── SearchAgent     (文件/知识库检索，3 种模式)
  ├── TerminologyAgent (术语标准化/转换/验证/建议)
  └── ComplianceAgent  (快速/标准/详细 3 级合规检查)
```

### 关键目录

```
backend/app/
  api/             # 19 个 API 模块
  agents/
    core/          # Agent 协议和注册表
    functional/    # 写作/评审/术语/合规 Agent
    orchestrator/  # 主控 + 意图识别 + 状态机 + 任务分解
    search/        # 搜索 Agent
  services/        # 业务逻辑 (LLM/文件系统/对话/上下文)
  tools/           # PDF 解析/向量存储/术语映射/合规检查/文档生成
  models/          # DeepSeek-R1 / BGE-Embedding / BGE-Rerank

frontend/src/
  components/editor/    # Tiptap 编辑器
  components/AICreation/ # AI 创作面板
  agents/               # 前端 Agent 逻辑
  services/             # API 服务
  stores/               # Zustand 状态管理
```

### 上下文系统 (4 层)

1. **元数据层** — 文档基本信息
2. **文档层** — 整文档结构
3. **页面层** — 当前页内容
4. **内容层** — 精确段落级检索

## 数据存储

文档按 `material_id` 组织（不是 project_id），材料可跨项目共享：
```
backend/data/
  documents/{material_id}/
    index.json         # 元数据
    content.html       # HTML 内容
    content.json       # 结构化内容
  uploads/             # 原始上传
  standards_parsed/    # QJ903 标准解析结果
```

## 当前进度

- 35 个 Feature，29 个已完成 (83%)
- 已跳过：PDM 集成、Windows 7 兼容、麒麟系统兼容、#49 (WASM PDF 预览)、#50 (E2E 测试)
