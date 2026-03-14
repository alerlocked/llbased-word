# 工艺文件项目 - 上线计划

> 版本: 1.1
> 更新时间: 2026-03-08

---

## 一、项目定位

**部署环境**：内网部署
**目标**：功能完备，前后端完备

---

## 二、当前状态

| 组件 | 状态 | 备注 |
|------|------|------|
| 后端 API | ✅ 完成 | SQLite 数据库 |
| 标准库管理 | ✅ 完成 | CRUD + 批量导入 |
| 前端 | ✅ 完成 | React + Vite |
| AI 接入 | ✅ 已配置 | DeepSeek API 服务已集成 |
| 部署脚本 | ✅ 完成 | Windows + Linux |

---

## 三、技术栈

- **后端**：FastAPI + SQLite
- **前端**：React + Vite + Ant Design
- **AI**：DeepSeek API（直接调用）
- **存储**：SQLite（离线项目，文件系统）

---

## 四、功能清单

### 核心功能
1. **文件上传** - PDF/Word/Excel 解析 ✅
2. **标准库管理** - 术语库、分类管理 ✅
3. **工艺文件撰写** - AI 辅助 ✅
4. **工艺文件审查** - AI 辅助 ✅

### 辅助功能
- 文档管理 ✅
- 导出功能 ✅
- 搜索功能 ✅

---

## 五、上线任务

| # | 任务 | 优先级 | 状态 | 完成时间 |
|---|------|--------|------|----------|
| 1 | 配置 DeepSeek API | high | ✅ 完成 | 2026-03-08 |
| 2 | 验证前后端运行 | high | ✅ 完成 | 2026-03-08 |
| 3 | 标准库前端集成 | high | ✅ 完成 | 2026-03-08 |
| 4 | AI 辅助撰写功能 | medium | ✅ 完成 | 2026-03-08 |
| 5 | 部署脚本 | medium | ✅ 完成 | 2026-03-08 |

---

## 六、验证详情

### 1. 前后端可运行验证 ✅
- **后端依赖**: `backend/requirements.txt` 完整
  - FastAPI 0.104.1 + Uvicorn
  - SQLAlchemy + SQLite
  - LangChain + ChromaDB
  - OpenAI SDK（用于 DeepSeek API）
  - PDF 解析库（PyPDF2, pdfplumber, pymupdf）

- **前端依赖**: `frontend/package.json` 完整
  - React 18 + TypeScript
  - Ant Design 5
  - Vite 5
  - Zustand 状态管理

- **启动脚本**:
  - `start.bat` - Windows 一键启动
  - `start_backend.bat` - 后端单独启动
  - `start_frontend.bat` - 前端单独启动
  - `stop.bat` - 停止所有服务

### 2. DeepSeek API 配置 ✅
- **配置文件**: `backend/.env`
- **模板文件**: `backend/.env.example` ✅ 新建
- **API 路由**: `/api/deepseek/`
  - `POST /chat` - 聊天补全
  - `POST /generate-document` - 生成工艺文档
  - `POST /align-terminology` - 术语对齐
  - `POST /check-compliance` - 合规检查
  - `GET /status` - 服务状态
- **服务实现**: `backend/app/services/deepseek_service.py`

### 3. 标准库前端集成 ✅
- **前端页面**: `frontend/src/pages/LibraryPage.tsx`
- **知识库组件**: `frontend/src/components/Library/KnowledgeBaseTab.tsx`
  - 文档上传（TXT/DOCX/PDF）
  - 文档列表展示
  - 文档删除
  - 数据同步
- **后端 API**: `/api/rag/`
  - `POST /upload-document` - 上传文档
  - `GET /documents` - 文档列表
  - `DELETE /document` - 删除文档
  - `POST /sync` - 数据同步
  - `GET /statistics` - 统计信息

### 4. AI 辅助撰写功能 ✅
- **前端页面**: `frontend/src/pages/AgentCreationPage.tsx`
  - 需求输入
  - 进度显示（5步骤）
  - 结果展示
  - 复制功能
- **后端 API**: `/api/agent/`
  - `POST /start-conversation` - 启动对话
  - `POST /reply-question` - 回复问题
  - `POST /select-plan` - 选择计划
  - `POST /confirm-materials` - 确认素材
  - `POST /apply-suggestions` - 应用建议
  - `POST /generate-stream` - 流式生成
  - `GET /task/{task_id}` - 任务状态

### 5. 部署脚本 ✅
- **Windows 脚本**:
  - `start.bat` - 启动所有服务
  - `stop.bat` - 停止所有服务
  - `install.bat` - 安装依赖
- **Linux 脚本**:
  - `deploy/internal_network/deploy.sh` - 内网部署
  - `deploy/internal_network/README.md` - 部署文档

---

## 七、部署方式

### Windows 快速启动
```bash
# 1. 安装依赖
install.bat

# 2. 配置 API 密钥
# 编辑 backend/.env 文件，设置 DEEPSEEK_API_KEY

# 3. 启动服务
start.bat

# 4. 访问应用
# 前端: http://localhost:3000
# API文档: http://localhost:8000/docs
```

### Linux 内网部署
```bash
# 1. 执行部署脚本
cd deploy/internal_network
chmod +x deploy.sh
./deploy.sh

# 2. 配置 API 密钥
vim backend/.env

# 3. 启动服务
./start_all.sh
```

---

## 八、待配置项

| 配置项 | 文件位置 | 说明 |
|--------|----------|------|
| DEEPSEEK_API_KEY | backend/.env | 必须配置，AI 功能依赖 |
| DASHSCOPE_API_KEY | backend/.env | 可选，语音识别功能 |
| ALIYUN_ACCESS_KEY | backend/.env | 可选，阿里云服务 |

---

## 九、下一步工作

1. **获取 DeepSeek API Key**
   - 访问 https://platform.deepseek.com/
   - 创建 API Key 并配置到 `backend/.env`

2. **首次启动测试**
   - 运行 `start.bat` 启动服务
   - 访问 http://localhost:3000 验证前端
   - 访问 http://localhost:8000/docs 验证 API

3. **功能验证**
   - 测试知识库文档上传
   - 测试 AI 辅助撰写功能
   - 测试工艺文档生成

---

*项目状态: 准备就绪，等待 API Key 配置后可上线*
