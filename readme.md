# 记者智能创作系统 (Journalist AI)

面向历史、地理、纪实类记者的专业AI创作工具，实现音频转写→智能整理→AI Agent自动创作的完整闭环。

## 🌟 核心特性

### 📝 音频转写与编辑
- **多格式支持**: MP3、WAV、M4A、AAC、FLAC、OGG
- **智能转写**: 集成阿里云通义千问ASR，精准时间戳
- **实时编辑**: 可视化波形编辑器，音频文本同步
- **片段管理**: 单个片段编辑、删除、新增，批量查找替换

### 🤖 AI Agent智能创作
- **自主工作流**: LangChain Agent自动协调需求分析→素材检索→大纲生成→内容撰写→质量评审
- **多角度分析**: 从历史、地理、经济、政治、民生、文化等6个维度深度分析需求
- **智能素材检索**: 
  - 本地转写库检索
  - 网络实时搜索 (DuckDuckGo)
  - RAG向量知识库检索
- **质量评审**: 多维度评分（内容、结构、语言、新闻价值、标题）

### 🎨 用户风格学习 ⭐
- **风格分析**: 从历史稿件中学习用户写作风格（句式、词汇、段落、语气等）
- **自动应用**: 生成文章时自动应用用户个人风格
- **持续精进**: 
  - 从用户编辑行为中学习偏好
  - 定期分析新文章，增量更新风格档案
  - 置信度逐步提高

### 📚 素材管理
- **项目管理**: 创建项目，添加多个转写素材
- **版本控制**: 编辑历史记录，支持版本对比
- **素材面板**: 可视化管理转写片段和搜索结果

## 🏗️ 技术架构

### 前端
- **框架**: React 18 + TypeScript + Vite
- **UI库**: Ant Design 5
- **状态管理**: Zustand
- **音频处理**: Wavesurfer.js
- **本地存储**: IndexedDB
- **路由**: React Router v6

### 后端
- **Web框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy ORM
- **异步任务**: Celery + Redis
- **AI引擎**: 
  - LangChain 0.1.0 (Agent框架)
  - 通义千问 qwen-plus (LLM)
  - 通义千问 qwen3-asr-flash (语音识别)
- **向量数据库**: ChromaDB
- **Embedding**: BAAI/bge-large-zh-v1.5 (本地)
- **网络搜索**: DuckDuckGo

### Agent系统架构

```
用户输入
    ↓
WritingMasterAgent (主控Agent)
    ├─ RequirementAnalyzer (需求分析)
    ├─ 工具调用
    │   ├─ LocalSearchTool (本地素材检索)
    │   ├─ WebSearchTool (网络搜索)
    │   └─ RAGRetrieverTool (知识库检索)
    ├─ OutlineGenerator (大纲生成)
    ├─ ContentWriter (内容撰写)
    │   ├─ StyleAnalyzer (风格分析)
    │   ├─ StyleApplier (风格应用)
    │   └─ StyleLearner (持续学习)
    └─ QualityReviewer (质量评审)
    ↓
完整文章 + 中间步骤
```

## 📦 项目结构

```
Journalist/
├── frontend/                    # React前端
│   ├── src/
│   │   ├── components/         # UI组件
│   │   │   ├── AudioEditor/   # 音频编辑器
│   │   │   ├── AudioPlayer/   # 音频播放器
│   │   │   ├── Creation/      # 创作组件
│   │   │   ├── Layout/        # 布局组件
│   │   │   └── Upload/        # 上传组件
│   │   ├── pages/             # 页面
│   │   │   ├── AgentCreationPage.tsx    # AI Agent创作
│   │   │   ├── AudioUploadPage.tsx      # 音频上传
│   │   │   ├── TranscribePage.tsx       # 转写编辑
│   │   │   ├── CreationPage.tsx         # 项目创作
│   │   │   ├── ProjectListPage.tsx      # 项目列表
│   │   │   └── ArticlePage.tsx          # 稿件生成
│   │   ├── stores/            # 状态管理
│   │   ├── services/          # API服务
│   │   └── db/                # IndexedDB
│   └── package.json
├── backend/                     # Python后端
│   ├── app/
│   │   ├── agents/             # LangChain Agent模块 ⭐
│   │   │   ├── master_agent.py           # 主控Agent
│   │   │   ├── sub_agents/               # 子Agent
│   │   │   │   ├── requirement_analyzer.py
│   │   │   │   ├── outline_generator.py
│   │   │   │   ├── content_writer.py
│   │   │   │   └── quality_reviewer.py
│   │   │   ├── tools/                    # Agent工具
│   │   │   │   ├── local_search.py
│   │   │   │   ├── web_search.py
│   │   │   │   ├── rag_retriever.py
│   │   │   │   └── knowledge_builder.py
│   │   │   └── style/                    # 风格学习系统 ⭐
│   │   │       ├── style_analyzer.py
│   │   │       ├── style_applier.py
│   │   │       └── style_learner.py
│   │   ├── api/                # API路由
│   │   │   ├── audio.py       # 音频管理
│   │   │   ├── transcribe.py  # 音频转写
│   │   │   ├── creation.py    # 创作管理
│   │   │   ├── article.py     # 稿件生成
│   │   │   └── agent.py       # AI Agent API ⭐
│   │   ├── models/            # 数据库模型
│   │   │   └── database.py    # 包含风格学习相关表
│   │   ├── services/          # 业务逻辑
│   │   │   ├── audio_service.py
│   │   │   ├── transcribe_service.py
│   │   │   └── llm_service.py
│   │   ├── tasks/             # Celery异步任务
│   │   │   └── transcribe_task.py
│   │   └── utils/             # 工具类
│   │       └── logger.py
│   ├── main.py                # 应用入口
│   ├── init_db.py             # 数据库初始化
│   └── requirements.txt       # Python依赖
├── install.bat                 # 安装脚本
├── start.bat                   # 启动脚本
├── start_celery.bat           # Celery启动脚本
├── stop.bat                    # 停止脚本
└── README.md

```

## 🚀 快速开始

### 环境要求

- **Python**: 3.10+
- **Node.js**: 16+
- **Redis**: 5.0+ (用于Celery)
- **Conda**: 推荐使用 (已配置journalist环境)

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd Journalist
   ```

2. **配置API密钥**
   ```bash
   # 复制环境变量模板
   cp backend/.env.example backend/.env
   
   # 编辑.env文件，填入以下密钥：
   # DASHSCOPE_API_KEY=your_dashscope_api_key
   ```

3. **运行安装脚本**
   ```bash
   # Windows
   install.bat
   
   # 该脚本会：
   # 1. 激活journalist conda环境
   # 2. 安装Python依赖（包括LangChain）
   # 3. 安装前端依赖
   # 4. 初始化数据库（包括风格学习表）
   ```

### 启动应用

```bash
# Windows - 启动所有服务
start.bat

# 该脚本会启动：
# 1. Redis服务器 (端口6379)
# 2. FastAPI后端 (端口8000)
# 3. Celery Worker (异步任务处理)
# 4. 前端开发服务器 (端口3000)
```

### 访问应用

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

### 停止应用

```bash
stop.bat
```

## 📖 使用指南

### 1. 音频转写流程

1. **上传音频**: 访问"音频上传"页面，上传音频文件
2. **开始转写**: 点击"开始转写"，系统自动调用通义千问ASR
3. **编辑转写**: 在转写编辑页面，可视化编辑音频和文本
4. **保存素材**: 完成编辑后保存，素材进入素材库

### 2. AI Agent智能创作 ⭐

1. **访问Agent创作页面**: `/agent-creation`
2. **输入创作需求**: 
   ```
   例如：写一篇关于某村传统水利工程保护的报道，1500字左右，要包含：
   1. 历史背景和文化价值
   2. 当前保护现状
   3. 面临的挑战
   4. 专家观点和建议
   5. 未来展望
   ```
3. **Agent自动工作**: 
   - 需求分析（多角度解析）
   - 素材检索（本地+网络+知识库）
   - 生成大纲（结构化设计）
   - 撰写内容（应用用户风格）
   - 质量评审（多维度评分）
4. **查看结果**: 获得完整文章和中间步骤详情

### 3. 项目创作流程

1. **创建项目**: 在项目列表页创建新项目
2. **添加素材**: 从转写库选择相关素材
3. **编辑内容**: 在编辑器中撰写和修改
4. **AI辅助**: 使用AI改写、扩写等功能
5. **版本管理**: 查看编辑历史，对比版本差异

### 4. 用户风格学习 ⭐

**首次使用**:
- 系统会分析您的历史文章（如果有）
- 建立初始风格档案

**持续学习**:
- 每次编辑AI生成的内容，系统学习您的修改偏好
- 定期（每月）自动分析新文章，更新风格档案
- 置信度逐步提高，生成内容越来越符合您的风格

**风格维度**:
- 句式特征（句长、长短句比例、修辞）
- 词汇特点（复杂度、正式程度、术语频率）
- 段落结构（长度、逻辑关系、过渡词）
- 叙述角度（人称、引语、客观性）
- 语气风格（正式度、情感色彩、节奏）
- 开篇结尾（习惯用法）

## 🗄️ 数据库设计

### 核心表

- `audio_files`: 音频文件
- `transcripts`: 转写记录
- `creation_projects`: 创作项目
- `materials`: 项目素材
- `editor_versions`: 编辑版本
- `articles`: 生成的稿件

### 风格学习表 ⭐

- `user_style_profiles`: 用户风格档案
  - 存储风格分析结果（JSON）
  - 样本文章ID列表
  - 置信度分数
  - 更新次数和时间

- `style_learning_logs`: 风格学习日志
  - 学习类型（初始/编辑/定期）
  - 原始内容和修改内容
  - 提取的偏好信息

## 🔧 配置说明

### 环境变量 (backend/.env)

```env
# 阿里云通义千问API密钥
DASHSCOPE_API_KEY=your_api_key_here

# 数据库配置（自动创建）
DATABASE_URL=sqlite:///path/to/journalist.db

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379

# Agent配置
AGENT_MAX_ITERATIONS=10
AGENT_TEMPERATURE=0.3

# Embedding模型
LOCAL_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
```

## 🐛 常见问题

### 1. 依赖冲突

**问题**: `opencv-python`和`langchain`的numpy版本冲突

**解决**: 保持`numpy 1.26.4`，忽略opencv警告（系统不使用opencv）

### 2. Redis连接失败

**问题**: Celery无法连接Redis

**解决**: 
- 确保Redis已启动
- 检查端口6379是否被占用
- Windows用户可使用WSL运行Redis

### 3. 转写失败

**问题**: 音频转写返回错误

**解决**:
- 检查DASHSCOPE_API_KEY是否正确
- 确认音频格式支持
- 查看后端日志详细错误信息

### 4. Agent生成超时

**问题**: AI Agent生成文章时间过长

**解决**:
- 正常情况1-3分钟
- 检查网络连接（网络搜索工具需要）
- 查看后端日志，确认Agent执行步骤

## 📊 系统监控

### 日志位置

- **后端日志**: 控制台输出（使用Winston）
- **Celery日志**: 单独窗口显示
- **前端日志**: 浏览器控制台

### 性能指标

- **转写速度**: 约1分钟音频/10秒
- **Agent生成**: 1-3分钟/篇
- **风格分析**: 30秒-1分钟/篇

## 🔐 数据安全

- **本地存储**: 所有数据100%存储在本地
- **加密传输**: API调用使用HTTPS
- **隐私保护**: 不上传原始音频到云端（仅转写时临时上传）

## 🛣️ 开发路线图

### 已完成 ✅

- [x] 音频上传与管理
- [x] 智能转写（通义千问ASR）
- [x] 可视化音频编辑器
- [x] 项目和素材管理
- [x] LangChain Agent系统
- [x] 用户风格学习与应用
- [x] RAG知识库检索
- [x] 多源素材检索
- [x] 质量评审系统

### 进行中 🚧

- [ ] 知识库自动构建（定时任务）
- [ ] 更多体裁模板
- [ ] 协作功能

### 计划中 📋

- [ ] 多用户系统
- [ ] 云端同步（可选）
- [ ] 移动端适配
- [ ] 插件系统

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 👥 联系方式

- 项目地址: [GitHub Repository]
- 问题反馈: [Issues]

---

**注意**: 本系统使用阿里云通义千问API，需要自行申请API密钥。首次使用建议先测试小规模数据。
