# 智能工艺文件辅助编辑系统 - Claude开发指南

## 项目概述

**项目名称**: 智能工艺文件辅助编辑系统 (Craft Document Assistant)
**项目类型**: 面向工艺师的专业AI辅助编辑工具
**核心功能**: 工艺意图→标准工艺术语→工艺文件生成的完整闭环
**Archon项目ID**: f9ecaf8b-ff17-467d-bf29-37aae558bb4e

## 功能定位

**不是替代PDM系统，而是PDM系统的智能辅助工具**：
- 帮助工艺师将脑海中的工艺方法转化为标准的工艺文件术语
- 提供智能化的文档生成和编辑支持
- 支持PDF工艺文档的高精度解析（≥97%准确性）
- 实现工艺知识的智能检索和应用

## 技术架构

### 前端技术栈
- **框架**: React 18 + TypeScript + Vite
- **UI库**: Ant Design 5
- **状态管理**: Zustand
- **音频处理**: Wavesurfer.js
- **本地存储**: IndexedDB + Dexie
- **路由**: React Router v6

### 后端技术栈
- **Web框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy ORM
- **异步任务**: Celery + Redis
- **AI引擎**:
  - LangChain 0.1.0 (Agent框架)
  - DeepSeek-R1 (14B/32B) 本地推理模型
  - BGE-Embedding + BGE-Rerank 本地向量模型
- **向量数据库**: ChromaDB
- **Embedding**: BAAI/bge-large-zh-v1.5 (本地) → 升级为 BGE系列模型

## Archon集成配置

### MCP配置
项目已配置Archon MCP连接：
- **配置文件**: `.claude-mcp.json`
- **MCP服务地址**: http://localhost:8051
- **项目ID**: f9ecaf8b-ff17-467d-bf29-37aae558bb4e
- **工作空间**: D:\ai_idea\localknowledgebase-word

### 开发流程集成
后续开发将使用Archon进行：
1. **任务管理**: 通过Archon创建和跟踪开发任务
2. **项目规划**: 使用Archon的规划功能
3. **执行跟踪**: 实时监控任务执行状态
4. **测试验证**: 集成测试结果到Archon

## 项目结构

```
craft-document-assistant/
├── frontend/                    # React前端
│   ├── src/
│   │   ├── components/         # UI组件库
│   │   ├── pages/             # 页面组件
│   │   ├── stores/            # Zustand状态管理
│   │   ├── services/          # API服务层
│   │   ├── config/            # API配置集中管理
│   │   ├── utils/             # 工具函数（含调试日志）
│   │   ├── db/                # IndexedDB本地存储
│   │   └── agents/            # Agent交互接口
├── backend/                     # Python后端
│   ├── app/
│   │   ├── api/               # FastAPI路由定义
│   │   ├── agents/            # LangChain Agent系统
│   │   │   ├── orchestrator/  # 主控Agent (Orchestrator)
│   │   │   ├── sub_agents/    # 子Agent模块
│   │   │   └── toolkits/      # 工具包
│   │   ├── services/          # 业务逻辑服务
│   │   ├── models/            # SQLAlchemy数据模型
│   │   ├── tasks/             # Celery定时任务
│   │   ├── shared/            # 共享模块（日志、配置）
│   │   ├── tools/             # 工具模块
│   │   └── utils/             # 工具函数库
│   └── tests/                 # 测试代码（镜像app结构）
├── module/                      # 存储模块（工艺文档）
├── test_data/                   # 测试PDF数据
├── .claude/                     # Claude开发规范
├── .claude-mcp.json            # Archon MCP配置
└── PRPs/                        # AI开发文档
```

## 核心功能模块

### 1. PDF工艺文档解析模块
- **高精度表格提取**: ≥97%的元素对应关系准确性
- **工艺术语识别**: 自动识别工具、量具、规格等关键信息
- **核心区域过滤**: 自动忽略页眉页脚等边缘内容
- **多格式支持**: 支持电缆装配、机械加工等工艺文档类型

### 2. AI Agent辅助编辑系统
- **主控Agent (Orchestrator)**: 负责会话状态机管理、意图识别、任务分解
- **子Agent**:
  - PDFParserAgent (PDF解析)
  - RAGRetrieverAgent (知识检索)
  - TerminologyAlignerAgent (术语对齐)
  - ComplianceCheckerAgent (合规检查)
  - DocumentGeneratorAgent (文档生成)
- **工艺知识库**: 本地向量数据库存储工艺标准和规范

### 3. PDM系统集成
- **数据交换接口**: 与现有PDM系统无缝集成
- **辅助而非替代**: 提供智能建议，最终决策由工艺师完成
- **标准化输出**: 生成符合企业标准的工艺文件格式

## 开发规范

### 日志规范
- **使用结构化日志**: `from app.shared.logging import get_logger`
- **禁止字符串格式化**: 使用关键字参数
- **正确示例**: `logger.info("user_created", user_id="123", role="admin")`
- **错误示例**: `logger.info(f"User {user_id} created")`
- **上下文绑定**: 使用 `bind_context()` 绑定请求级数据

### 测试规范
- **测试目录**: `backend/tests/` 镜像 `backend/app/` 结构
- **单元测试**: 使用 `@pytest.mark.unit` 标记
- **集成测试**: 使用 `@pytest.mark.integration` 标记
- **运行测试**: `cd backend && python -m pytest tests/ -v`

### 代码规范
- **类型注解**: 使用TypeScript和Python类型注解
- **错误处理**: 使用结构化异常处理
- **API设计**: 使用FastAPI的Pydantic模型

## Archon开发流程

### 1. 创建开发计划
```bash
# 使用Archon创建项目计划
/create-plan "需求描述"
```

### 2. 任务管理
- 任务在Archon中创建和跟踪
- 每个任务有明确的状态（todo/doing/review/done）
- 任务间可以设置依赖关系

### 3. 执行与验证
- 按照Archon中的任务顺序执行
- 每个任务完成后进行验证
- 测试结果记录到Archon

### 4. 项目监控
- 实时查看项目进度
- 代码质量指标跟踪
- 开发效率分析

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 16+
- Redis 5.0+
- Archon服务已启动

### 安装项目
```bash
# 运行安装脚本
install.bat

# 配置API密钥
cp backend/.env.example backend/.env
# 编辑 .env 文件，填入 DASHSCOPE_API_KEY
```

### 启动项目
```bash
# 启动所有服务
start.bat

# 访问应用
# 前端: http://localhost:3000
# API文档: http://localhost:8000/docs
# Archon UI: http://localhost:3737
```

## 关键文件

### 后端核心文件
- `backend/main.py`: FastAPI应用入口
- `backend/app/agents/master_agent.py`: 主控Agent
- `backend/app/api/`: API路由定义
- `backend/app/shared/logging.py`: 结构化日志模块
- `backend/app/shared/config.py`: 共享配置模块

### 前端核心文件
- `frontend/src/pages/`: 页面组件
- `frontend/src/components/`: UI组件
- `frontend/src/services/`: API服务
- `frontend/src/utils/debugLogger.ts`: 调试日志工具
- `frontend/src/config/api.ts`: API配置

### 配置文件
- `.claude-mcp.json`: Archon MCP配置
- `backend/pytest.ini`: 测试配置
- `backend/.env`: 环境变量

## 开发工具

### AI Agent工具
- **codebase-analyst**: 代码库分析专家
- **validator**: 功能验证专家

### Archon集成命令
- 项目管理和任务跟踪
- 开发计划创建和执行
- 测试结果记录和分析

## 注意事项

### API密钥管理
- 阿里云通义千问API密钥存储在 `.env` 文件中
- 切勿将API密钥提交到版本控制

### 数据安全
- 所有数据100%本地存储
- 音频文件仅在转写时临时上传到云端

### Archon集成
- 开发任务通过Archon进行管理
- 每个功能开发都是完整的计划-执行-测试循环
- 项目进度在Archon UI中实时可见

## 开发路线图

### 当前阶段：架构升级完成 ✅
- 现有记者系统架构成功升级为工艺文件辅助编辑系统
- 主控Agent + 子Agent架构已建立
- PDF解析和工艺术语识别功能已验证（100%准确性）
- Archon任务管理集成完成

### 下一阶段：功能完善和部署
- 完成所有20个核心任务的开发
- 实现Windows 7和麒麟系统兼容性
- 部署DeepSeek-R1和BGE系列本地模型
- 进行完整的端到端测试和验证

## 技术支持

- **Archon文档**: 查看Archon UI中的帮助文档
- **日志调试**: 使用结构化日志进行问题排查
- **测试验证**: 运行测试确保功能正确
- **MCP集成**: 通过MCP协议与Archon交互

---

*最后更新: 2026-02-16*
*Archon项目ID: f9ecaf8b-ff17-467d-bf29-37aae558bb4e*