# 工艺文件辅助编辑系统

> 工艺意图 → 标准工艺术语 → 工艺文件生成

## Repo

- GitHub: `alerlocked/llbased-word`（**public**，`main` 受 branch protection 保护，禁直推走 PR）
- Project Board: https://github.com/users/alerlocked/projects/1
- 主干: `main`
- 协作流程: 见 [CONTRIBUTING.md](CONTRIBUTING.md)（分支模型 / PR + review / ⭐架构层隔离清单 / commit 规范 / 新协作者入门）

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + Tiptap 2 |
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + SQLite |
| AI | LangChain + GLM-5 |
| PDF | MinerU 3.4 (VLM 高精度解析) |
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

> **架构单一源**:见 [ARCHITECTURE.md](ARCHITECTURE.md) —— Agent 系统 / 生成流程 / 上下文检索 / 数据存储 / 前端 / 运行,反映代码真实状态。本文不重复架构。

**架构维护规范**:涉及架构改动(agents / 检索 / 数据 / 生成流程),lead 收尾**必须更新 `ARCHITECTURE.md`**;DEV-LOG「当前状态」记架构变更点。

## 进度 / 状态

见 [DEV-LOG.md](DEV-LOG.md)(当前任务 / 历史决策)。
