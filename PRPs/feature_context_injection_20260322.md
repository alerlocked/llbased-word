# PRP: AI 助手上下文注入功能

**创建时间**: 2026-03-22
**任务类型**: 功能增强
**优先级**: High
**预计工时**: 3-5 天

---

## 一、需求背景

### 1.1 问题

当前 AI 助手（`/agent/generate-stream`）调用 LLM 时，**没有注入工艺文档上下文**，导致：
- 用户询问工艺参数时，AI 无法回答
- 用户要求生成工艺文件时，AI 没有参考素材
- 浪费了现有的 `exports_html` 数据（文档级 HTML + 语义索引）

### 1.2 目标

实现**分层索引 + 渐进式披露**的上下文注入，遵循 Anthropic 2025-2026 最佳实践：
- **Just-in-Time Retrieval**: 运行时动态加载，不预先塞满上下文
- **Progressive Disclosure**: 让 AI 逐步发现相关上下文
- **Attention Budget 管理**: 最小化高信号 token 集合

---

## 二、现有资源

### 2.1 数据结构

**目录**: `data/exports_html/`

每个 PDF 对应一个目录：
```
data/exports_html/
  ├── 全弹设备电缆装配工艺/
  │   ├── document.html      # 完整 HTML（包含所有表格）
  │   ├── index.json         # 语义索引
  │   └── images/            # 图片资源
```

**index.json 结构**:
```json
{
  "name": "全弹设备电缆装配工艺",
  "file_name": "全弹设备电缆装配工艺.pdf",
  "pages": 44,
  "tables": [
    {
      "id": "G4a",
      "type": "工艺文件目录",
      "page": 2,
      "summary": "工艺文件目录包含产品基本信息"
    },
    {
      "id": "G5a",
      "type": "工艺文件目录",
      "page": 3,
      "summary": "G5a 配套表"
    }
  ],
  "processes": [],
  "materials": ["GD414", "润滑脂", "乐泰", "无水乙醇", "清洗剂"],
  "generated_at": "2026-03-21T23:41:04.505808",
  "html_file": "document.html"
}
```

### 2.2 现有代码

| 文件 | 功能 | 问题 |
|------|------|------|
| `context_manager.py` | 文档管理 | 使用 `exports_vlm_full`，不是 `exports_html` |
| `context_builder.py` | 上下文构建 | 简单截断，无分层加载 |
| `agent.py` | AI 助手 API | 没有注入工艺文档上下文 |

---

## 三、分层上下文加载方案

### 3.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Layer 0: 元信息索引                     │
│  所有文档的名称 + 表格ID列表 + 材料列表                       │
│  Token: ~500 | 会话启动时加载                                │
├─────────────────────────────────────────────────────────────┤
│                      Layer 1: 表格索引                       │
│  表格 ID → 类型 → 页码 → 摘要                                │
│  Token: ~2000 | 会话级缓存（首次查询时加载）                  │
├─────────────────────────────────────────────────────────────┤
│                      Layer 2: 按需加载表格                   │
│  根据用户查询匹配相关表格，加载 HTML                          │
│  Token: ~5000-20000 | 动态加载（每次查询）                   │
├─────────────────────────────────────────────────────────────┤
│                      Layer 3: 精确检索                       │
│  参数搜索、关键词匹配、全文搜索                               │
│  Token: ~500-2000 | 按需（当 Layer 2 不足时）                │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 上下文注入流程

```python
def build_agent_context(query: str, session_id: str, max_tokens: int = 15000):
    context = []
    used_tokens = 0
    
    # Layer 0: 元信息索引（始终加载）
    if not session_has_layer0(session_id):
        meta = load_all_document_meta()  # ~500 tokens
        context.append(meta)
        used_tokens += 500
        session_set_layer0_loaded(session_id)
    
    # Layer 1: 表格索引（会话级加载一次）
    if not session_has_layer1(session_id):
        table_index = load_table_index()  # ~2000 tokens
        context.append(table_index)
        used_tokens += 2000
        session_set_layer1_loaded(session_id)
    
    # Layer 2: 按需加载相关表格
    matched_tables = search_relevant_tables(query)
    for table in matched_tables:
        if used_tokens + table.tokens < max_tokens:
            html = extract_table_html(table.doc_name, table.id)
            context.append(html)
            used_tokens += table.tokens
    
    # Layer 3: 精确检索（如果有参数关键词）
    if has_parameter_keywords(query):
        params = search_parameters(query)
        context.append(params)
        used_tokens += params.tokens
    
    return "\n\n---\n\n".join(context)
```

### 3.3 AI 助手 API 改造

**原流程**:
```
用户输入 → 调用 LLM → 返回响应
```

**新流程**:
```
用户输入 → 构建上下文（分层加载）→ 注入到 prompt → 调用 LLM → 返回响应
```

---

## 四、实现方案

### 4.1 新增文件

**`backend/app/services/hierarchical_context.py`** - 分层上下文管理器
```python
class HierarchicalContext:
    """分层上下文管理器"""
    
    def __init__(self, data_dir: str = "data/exports_html"):
        self.data_dir = Path(data_dir)
        self._meta_cache = None  # Layer 0 缓存
        self._table_index_cache = None  # Layer 1 缓存
    
    def load_meta_index(self) -> str:
        """加载 Layer 0: 元信息索引"""
        pass
    
    def load_table_index(self) -> str:
        """加载 Layer 1: 表格索引"""
        pass
    
    def search_tables(self, query: str) -> List[TableMatch]:
        """搜索相关表格"""
        pass
    
    def extract_table_html(self, doc_name: str, table_id: str) -> str:
        """提取单个表格的 HTML"""
        pass
    
    def build_context(
        self, 
        query: str, 
        session_id: str, 
        max_tokens: int = 15000
    ) -> str:
        """构建分层上下文"""
        pass
```

### 4.2 修改文件

#### 4.2.1 `backend/app/api/agent.py`

**位置**: `/generate-stream` 端点

**修改前**:
```python
@router.post("/generate-stream")
async def generate_stream(request: GenerateStreamRequest):
    # ...
    result = await llm_service.generate_text(
        prompt=full_prompt,
        temperature=0.7,
        max_tokens=2000
    )
```

**修改后**:
```python
from app.services.hierarchical_context import hierarchical_context

@router.post("/generate-stream")
async def generate_stream(request: GenerateStreamRequest):
    # ...
    
    # 构建分层上下文
    doc_context = hierarchical_context.build_context(
        query=user_input,
        session_id=session_id,
        max_tokens=15000
    )
    
    # 注入到 prompt
    full_prompt = f"""{system_prompt}

## 参考文档

{doc_context}

## 用户问题

{user_input}

请基于参考文档回答用户问题。如果参考文档中没有相关信息，请如实告知。"""
    
    result = await llm_service.generate_text(
        prompt=full_prompt,
        temperature=0.7,
        max_tokens=2000
    )
```

#### 4.2.2 `backend/app/services/context_manager.py`

**修改**: 支持 `exports_html` 目录

**新增方法**:
```python
def load_exports_html_index(self, doc_name: str) -> Dict:
    """加载 exports_html 的 index.json"""
    index_path = self.exports_html_dir / doc_name / "index.json"
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_table_from_html(self, doc_name: str, table_id: str) -> str:
    """从 document.html 中提取指定表格"""
    # 使用 BeautifulSoup 解析 HTML
    # 根据 table_id 提取对应表格
    pass
```

---

## 五、测试验证步骤

### 5.1 单元测试

**测试文件**: `backend/tests/test_hierarchical_context.py`

```python
def test_load_meta_index():
    """测试 Layer 0 加载"""
    ctx = HierarchicalContext()
    meta = ctx.load_meta_index()
    assert "文档列表" in meta
    assert len(meta) < 1000  # 确保不超过 500 tokens

def test_load_table_index():
    """测试 Layer 1 加载"""
    ctx = HierarchicalContext()
    index = ctx.load_table_index()
    assert "G4a" in index
    assert len(index) < 3000  # 确保不超过 2000 tokens

def test_search_tables():
    """测试表格搜索"""
    ctx = HierarchicalContext()
    results = ctx.search_tables("G4a")
    assert len(results) > 0
    assert results[0].table_id == "G4a"

def test_extract_table_html():
    """测试表格 HTML 提取"""
    ctx = HierarchicalContext()
    html = ctx.extract_table_html("全弹设备电缆装配工艺", "G4a")
    assert "<table" in html
    assert len(html) < 50000  # 确保不会太大

def test_build_context():
    """测试完整上下文构建"""
    ctx = HierarchicalContext()
    context = ctx.build_context("G4a 是什么？", session_id="test")
    assert "G4a" in context
    assert len(context) < 20000  # 确保不超过 max_tokens
```

### 5.2 集成测试

**测试场景**:

1. **基础问答**
   - 用户问："G4a 表格是什么？"
   - 预期：AI 能回答"G4a 是工艺文件目录，包含产品基本信息"

2. **参数查询**
   - 用户问："GD414 密封胶在哪里使用？"
   - 预期：AI 能从材料列表和表格中找到相关信息

3. **表格内容查询**
   - 用户问："第 5 页的表格内容是什么？"
   - 预期：AI 能加载并总结该页表格内容

4. **多轮对话**
   - 第一轮："列出所有文档"
   - 第二轮："G4a 的详细内容"
   - 预期：Layer 0/1 只加载一次，后续查询复用缓存

### 5.3 性能测试

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| Layer 0 加载时间 | < 50ms | 计时测试 |
| Layer 1 加载时间 | < 100ms | 计时测试 |
| Layer 2 表格提取 | < 200ms | 计时测试 |
| 完整上下文构建 | < 500ms | 计时测试 |
| Token 数量 | < 20000 | `estimate_tokens()` |

### 5.4 手动验证

**启动服务**:
```bash
cd D:\Project Nantianmen\projects\localknowledgebase-word\backend
python main.py
```

**测试 API**:
```bash
curl -X POST http://localhost:8000/agent/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"content": "G4a 表格是什么？", "session_id": "test-123"}'
```

**验证点**:
- [ ] 日志显示 Layer 0/1 加载
- [ ] 响应包含文档信息
- [ ] 第二次查询复用缓存
- [ ] Token 数量在限制内

---

## 六、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| HTML 解析失败 | 无法提取表格 | 使用 BeautifulSoup 容错解析 |
| Token 超限 | LLM 调用失败 | 实现动态截断策略 |
| 缓存失效 | 性能下降 | 使用 Redis 替代内存缓存 |
| 表格 ID 不唯一 | 提取错误 | 使用页码 + ID 组合定位 |

---

## 七、后续优化

### 7.1 短期（1-2 周）
- [ ] 实现 BM25 + Embedding 混合检索
- [ ] 添加表格内容 embedding 索引
- [ ] 优化表格 HTML 提取性能

### 7.2 中期（3-4 周）
- [ ] 添加 Contextual Embeddings（Anthropic 推荐）
- [ ] 实现 reranking 提升检索精度
- [ ] 添加会话级上下文管理（Redis）

### 7.3 长期（4-6 周）
- [ ] 实现智能体自主探索（Progressive Disclosure）
- [ ] 添加用户反馈循环
- [ ] 优化 token 使用效率（动态调整各层 token 分配）

---

## 八、成本估算

| 方案 | 每次查询 tokens | 每次查询成本 |
|------|----------------|-------------|
| 全量加载（100 PDFs） | ~2-3M | $10-30 |
| 基础 RAG | ~5K-20K | $0.02-0.1 |
| **分层索引 + 渐进披露（本方案）** | **~10K-30K** | **$0.05-0.15** |

**节省**: 99%+ 成本，同时保持高准确率

---

## 九、项目信息

**工作目录**: `D:\Project Nantianmen\projects\localknowledgebase-word`

**关键文件**:
- 新增: `backend/app/services/hierarchical_context.py`
- 修改: `backend/app/api/agent.py`
- 修改: `backend/app/services/context_manager.py`
- 测试: `backend/tests/test_hierarchical_context.py`

**参考资源**:
- 调研报告: `memory/document-context-injection-research-2026-latest.md`
- 数据目录: `data/exports_html/`

---

**状态**: ✅ PRP 已完成，等待开发
