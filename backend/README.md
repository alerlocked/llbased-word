# 智能工艺文件辅助编辑系统 - 后端

## 概述

本项目是面向工艺师的专业AI辅助编辑工具，核心功能是将工艺意图转化为标准的工艺文件术语，并提供智能化的文档生成和编辑支持。

## 功能特性

### 1. PDF工艺文档解析
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

### 3. CSV导出功能 (新增)
- **表格数据导出**: 支持将提取的表格导出为CSV格式
- **Excel兼容**: UTF-8 BOM编码确保Excel正确显示中文
- **批量导出**: 支持多个文档的批量CSV导出
- **混合解析**: 智能选择PyMuPDF或pdfplumber进行最佳提取

## 技术架构

### 后端技术栈
- **Web框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy ORM
- **异步任务**: Celery + Redis
- **AI引擎**:
  - LangChain 0.1.0 (Agent框架)
  - DeepSeek-R1 (14B/32B) 本地推理模型
  - BGE-Embedding + BGE-Rerank 本地向量模型
- **向量数据库**: ChromaDB
- **PDF解析**: PyMuPDF + pdfplumber (混合引擎)

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 16+
- Redis 5.0+
- Archon服务已启动

### 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

### 配置环境
```bash
cp .env.example .env
# 编辑 .env 文件，填入 DASHSCOPE_API_KEY
```

### 启动服务
```bash
# 启动API服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 启动Celery任务队列
celery -A main.celery_app worker --loglevel=info
```

### 运行测试
```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行PDF解析相关测试
python -m pytest tests/tools/test_pdfplumber_extractor.py -v
python -m pytest tests/tools/test_csv_export.py -v
python -m pytest tests/test_hybrid_parsing.py -v
```

## API文档

访问 `http://localhost:8000/docs` 查看完整的API文档。

### 主要API端点
- `GET /api/process-documents/` - 列出所有工艺文档
- `GET /api/process-documents/{doc_id}/extracted` - 获取提取内容
- `POST /api/process-documents/{doc_id}/export-csv` - 导出CSV
- `GET /api/process-documents/{doc_id}/csv/{export_id}` - 下载CSV

## 目录结构

```
backend/
├── app/                    # 应用代码
│   ├── api/               # FastAPI路由
│   ├── agents/            # LangChain Agent系统
│   │   ├── orchestrator/  # 主控Agent
│   │   └── sub_agents/    # 子Agent模块
│   ├── services/          # 业务逻辑服务
│   ├── models/            # 数据模型
│   ├── tasks/             # Celery定时任务
│   ├── shared/            # 共享模块
│   ├── tools/             # 工具模块
│   │   └── table_extractors/  # 表格提取器
│   └── utils/             # 工具函数库
├── tests/                 # 测试代码
│   ├── tools/            # 工具测试
│   └── test_hybrid_parsing.py  # 混合解析测试
├── docs/                  # 文档
│   └── pdf-parsing.md    # PDF解析文档
├── requirements.txt       # 依赖包
└── main.py                # 应用入口
```

## 开发规范

### 日志规范
- 使用结构化日志: `from app.shared.logging import get_logger`
- 禁止字符串格式化: 使用关键字参数
- 正确示例: `logger.info("user_created", user_id="123", role="admin")`
- 错误示例: `logger.info(f"User {user_id} created")`

### 测试规范
- 测试目录: `backend/tests/` 镜像 `backend/app/` 结构
- 单元测试: 使用 `@pytest.mark.unit` 标记
- 集成测试: 使用 `@pytest.mark.integration` 标记
- 运行测试: `cd backend && python -m pytest tests/ -v`

### 代码规范
- 类型注解: 使用Python类型注解
- 错误处理: 使用结构化异常处理
- API设计: 使用FastAPI的Pydantic模型

## CSV导出配置

### 配置选项
在 `app/shared/config.py` 中配置:

```python
CSV_EXPORT_CONFIG = {
    "encoding": "utf-8-sig",        # UTF-8 with BOM for Excel
    "delimiter": ",",               # CSV分隔符
    "quotechar": '"',               # 引用字符
    "include_metadata": True,        # 包含元数据
    "include_headers": True,         # 包含表头
    "date_format": "%Y-%m-%d",      # 日期格式
    "max_rows_per_file": 100000     # 单文件最大行数
}
```

### 使用示例
```python
from app.services.csv_export_service import CSVExportService

# 创建导出服务
csv_service = CSVExportService()

# 导出表格
result = csv_service.export_table_to_csv(table, "output.csv")
```

## 故障排除

### 常见问题
1. **PDF解析失败**: 检查PDF文件是否有效，是否为扫描件
2. **中文显示乱码**: 确保使用UTF-8 BOM编码 (`utf-8-sig`)
3. **内存不足**: 对于大文档，启用流式处理或增加内存限制
4. **表格提取不准确**: 调整`table_detection_threshold`或手动指定解析器

### 调试命令
```bash
# 查看详细日志
python -m pytest tests/ -v -s

# 检查依赖版本
pip list | grep -E "(pymupdf|pdfplumber|pandas)"

# 验证PDF文件
python -c "import fitz; doc = fitz.open('test.pdf'); print(f'Pages: {len(doc)}')"
```

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -am 'Add some feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 [MIT License](LICENSE).

## 技术支持

- **Archon文档**: 查看Archon UI中的帮助文档
- **日志调试**: 使用结构化日志进行问题排查
- **测试验证**: 运行测试确保功能正确
- **MCP集成**: 通过MCP协议与Archon交互