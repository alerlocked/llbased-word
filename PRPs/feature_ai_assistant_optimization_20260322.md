# PRP: AI 助手优化 - 问答/写作分离 + 关联检索增强

**日期**: 2026-03-22
**类型**: feature
**优先级**: high
**状态**: pending

---

## 背景

上下文注入功能已完成，但 Web 测试发现以下问题需要优化：

1. **智能写作 vs 问答模式混淆** - 对话框输出带修改标记（+28/-11），应该区分"问答"和"写作"两种模式
2. **关联查询不完整** - 问"装配工艺卡片有多少页"时，AI 没有关联 G4a 表格中的具体信息
3. **输出风格不简洁** - 问答模式下输出过长，用户只想快速获取信息
4. **前端无加载提示** - "正在加载上下文"只在后端日志，前端用户感知不到

---

## 现有代码

### 后端
- `backend/app/api/agent.py` - AI 助手 API（`/generate-stream` 接口）
- `backend/app/services/hierarchical_context.py` - 分层上下文管理器

### 前端
- `frontend/src/components/AICreation/AIChatPanel.tsx` - AI 聊天面板

---

## 问题分析

### 问题 1: 问答/写作模式混淆

**现状分析**：
1. `agent.py` 第 246-265 行：系统提示词只有单一角色定义
2. `AIChatPanel.tsx` 第 432 行：用户输入自动加 `[智能写作]` 前缀
3. `AIChatPanel.tsx` 第 544 行：生成结果自动触发 `onPreviewContent` 显示 InlineDiff

**问题**：所有输入都被当作"写作"处理，导致：
- 简单问题（如"有多少页"）也显示修改预览
- 用户无法区分"询问信息"和"生成内容"

### 问题 2: 关联查询不完整

**现状分析**：
`hierarchical_context.py` 第 165-205 行 `search_tables` 方法：
```python
# 匹配规则：
# 1. 表格 ID 精确匹配（如 "G4a"）
# 2. 表格类型匹配（如 "工艺卡片"）
# 3. 摘要关键词匹配
# 4. 材料名称匹配
```

**问题**：
- 关键词提取使用简单的 `\w+` 正则，中文字符被拆成单字
- "装配工艺卡片" 无法匹配到 "工艺卡片" 类型
- 没有利用 index.json 中的元信息（文档名称、材料列表）
- 查询 "多少页" 时，应优先返回元信息而非表格内容

### 问题 3: 输出风格不简洁

**现状分析**：
`agent.py` 第 246-260 行系统提示词：
```python
system_prompt = """你是一位专业的工艺文件编辑助手。你的职责是帮助工艺师：
1. 理解和整理工艺意图
2. 将口语化的描述转化为标准的工艺术语
3. 生成规范化的工艺文件内容
"""
```

**问题**：
- 提示词主要针对"写作"场景
- 没有强调"问答"场景的简洁性
- 缺少根据模式调整输出风格的指令

### 问题 4: 前端无加载提示

**现状分析**：
`agent.py` 第 296-298 行：
```python
yield f"data: {json.dumps({'type': 'progress', 'node': 'context_loader', 'message': '正在加载工艺文档上下文...'})}\n\n"
```

**问题**：
- 进度消息已发送，但前端 `AIChatPanel.tsx` 没有处理 `node === 'context_loader'` 的进度
- 第 459-478 行只处理 `planner/retriever/writer/reviewer` 节点

---

## 解决方案

### 方案 1: 问答/写作模式分离

**后端改动**（`agent.py`）：

1. **增加模式检测函数**：
```python
def detect_mode(user_input: str) -> str:
    """检测用户意图模式
    
    Returns:
        'qa' - 问答模式（询问信息）
        'write' - 写作模式（生成内容）
    """
    qa_keywords = ['多少', '是什么', '有没有', '在哪个', '哪些', '怎么', '为什么', '是否', '吗']
    write_keywords = ['写', '生成', '创建', '帮我', '修改', '优化', '完善']
    
    input_lower = user_input.lower()
    
    # 优先检测问答模式
    for keyword in qa_keywords:
        if keyword in input_lower:
            return 'qa'
    
    # 检测写作模式
    for keyword in write_keywords:
        if keyword in input_lower:
            return 'write'
    
    # 默认：短句（<20字）为问答，长句为写作
    return 'qa' if len(user_input) < 20 else 'write'
```

2. **根据模式调整系统提示词**：
```python
def get_system_prompt(mode: str) -> str:
    if mode == 'qa':
        return """你是一位专业的工艺文件知识助手。

## 回答原则
- **简洁优先**：直接回答问题，不要展开太多背景
- **基于文档**：优先使用参考文档中的信息
- **引用来源**：如果提到表格或文档，请注明来源（如"根据 G4a 表格"）
- **不知即说**：如果参考文档中没有相关信息，如实告知

## 禁止
- 不要生成长篇大论
- 不要输出修改标记（+/- 行号）
- 不要生成可编辑的文档内容
"""
    else:
        return """你是一位专业的工艺文件编辑助手。

## 写作原则
- **专业规范**：使用标准的工艺术语和格式
- **结构清晰**：合理分段，使用标题和列表
- **基于文档**：参考已有文档的风格和内容
- **可编辑性**：生成的内容应便于后续修改

## 输出格式
- 生成完整的工艺文件内容
- 可以包含占位符供用户填写（如 [待补充]）
"""
```

3. **返回模式标识**：
```python
mode = detect_mode(user_input)
yield f"data: {json.dumps({'type': 'mode', 'mode': mode})}\n\n"
```

**前端改动**（`AIChatPanel.tsx`）：

1. **接收模式消息**：
```typescript
// 第 459 行附近添加
} else if (data.type === 'mode') {
  currentMode = data.mode  // 保存当前模式
```

2. **根据模式决定是否预览**：
```typescript
// 第 544 行修改
if (contentAccumulator && onPreviewContent && currentMode === 'write') {
  onPreviewContent(contentAccumulator)
  message.success('生成完成，请在编辑器中预览并确认')
}
```

**文件修改清单**：
- `backend/app/api/agent.py` - 增加模式检测，调整提示词
- `frontend/src/components/AICreation/AIChatPanel.tsx` - 处理模式消息，条件预览

---

### 方案 2: 关联检索增强

**后端改动**（`hierarchical_context.py`）：

1. **改进中文分词**：
```python
import jieba

def extract_keywords(text: str) -> Set[str]:
    """提取关键词（支持中文）"""
    # 使用 jieba 分词
    words = jieba.cut(text)
    # 过滤停用词和单字
    stopwords = {'的', '了', '是', '有', '在', '我', '你', '他', '这', '那'}
    return {w.lower() for w in words if len(w) > 1 and w not in stopwords}
```

2. **增加元信息查询支持**：
```python
def search_meta_info(self, query: str) -> Optional[str]:
    """查询元信息（文档页数、材料列表等）
    
    适用于：
    - "XX文档有多少页"
    - "有哪些材料"
    - "XX表格在哪个文档"
    """
    documents = self._get_all_documents()
    
    # 检测查询类型
    if '多少页' in query or '页数' in query:
        # 提取文档名或表格 ID
        for doc in documents:
            doc_name = doc.get('name', '')
            if doc_name in query:
                return f"{doc_name} 共有 {doc.get('pages', '未知')} 页"
            
            # 检查表格
            for table in doc.get('tables', []):
                if table.get('id', '') in query:
                    return f"{table.get('id')} 在 {doc_name} 第 {table.get('page')} 页"
    
    return None
```

3. **改进 search_tables 方法**：
```python
def search_tables(self, query: str, top_k: int = 5) -> List[TableMatch]:
    # 使用改进的关键词提取
    query_keywords = extract_keywords(query)
    
    # 增加：复合关键词匹配（如"装配工艺卡片" = "装配" + "工艺卡片"）
    # 增加：表格类型模糊匹配（"工艺卡片" 匹配 "装配工艺卡片"）
    # 增加：文档名称匹配
```

4. **在 build_context 中优先使用元信息**：
```python
def build_context(self, query: str, session_id: str, max_tokens: int = 15000) -> str:
    # 先尝试元信息查询
    meta_answer = self.search_meta_info(query)
    if meta_answer:
        return f"# 快速回答\n\n{meta_answer}\n\n---\n\n# 详细信息\n\n..."
    
    # 原有逻辑...
```

**依赖添加**：
- `requirements.txt` 增加 `jieba>=0.42.1`

**文件修改清单**：
- `backend/app/services/hierarchical_context.py` - 改进检索逻辑
- `backend/requirements.txt` - 增加 jieba 依赖

---

### 方案 3: 简洁输出风格

**后端改动**（`agent.py`）：

已在方案 1 的提示词中解决：
- 问答模式提示词强调"简洁优先"
- 禁止生成长篇大论和修改标记

**额外优化**：
```python
# 在问答模式的提示词中增加示例
qa_prompt_examples = """

## 回答示例

用户：装配工艺卡片有多少页？
助手：根据文档信息，装配工艺卡片共有 15 页。（简洁，引用来源）

用户：G4a 表格包含哪些信息？
助手：G4a 表格包含车削工艺参数，包括切削速度、进给量、切削深度等。（直接列出关键信息）
"""
```

---

### 方案 4: 前端加载提示

**后端改动**（`agent.py`）：

已在代码中发送进度消息，无需修改。

**前端改动**（`AIChatPanel.tsx`）：

1. **处理 context_loader 进度**：
```typescript
// 第 459 行附近修改
} else if (data.type === 'progress') {
  if (data.node === 'context_loader') {
    // 新增：显示上下文加载提示
    stepsAccumulator[0].status = 'process'
    stepsAccumulator[0].description = data.message || '正在加载上下文...'
  } else if (data.node === 'planner') {
    // 原有逻辑...
```

2. **增加视觉提示**：
```typescript
// 在输入框上方显示加载状态
{loading && stepsAccumulator[0]?.description && (
  <div style={{ padding: '8px 16px', background: colors.primaryLight, borderRadius: 8 }}>
    <Spin size="small" /> {stepsAccumulator[0].description}
  </div>
)}
```

**文件修改清单**：
- `frontend/src/components/AICreation/AIChatPanel.tsx` - 处理加载进度

---

## 实施计划

### Phase 1: 后端核心改动（1-2 小时）
1. 修改 `agent.py`：增加模式检测 + 提示词分离
2. 修改 `hierarchical_context.py`：改进检索逻辑 + 元信息查询
3. 添加 `jieba` 依赖

### Phase 2: 前端改动（1 小时）
1. 修改 `AIChatPanel.tsx`：处理模式消息 + 条件预览 + 加载提示

### Phase 3: 测试验证（30 分钟）
1. 测试问答模式：
   - "装配工艺卡片有多少页？"
   - "G4a 表格包含哪些信息？"
2. 测试写作模式：
   - "帮我写一个车削工艺卡片"
   - "生成装配工艺流程"
3. 测试加载提示显示

---

## 测试验证

### 测试用例 1: 问答模式
**输入**: "装配工艺卡片有多少页？"
**期望**:
- 模式检测为 `qa`
- 输出简洁（1-2 句话）
- 引用文档来源
- 不触发预览

### 测试用例 2: 写作模式
**输入**: "帮我写一个车削工艺卡片"
**期望**:
- 模式检测为 `write`
- 输出完整工艺文件
- 触发预览模式
- 显示修改标记

### 测试用例 3: 关联查询
**输入**: "G4a 表格在哪个文档？"
**期望**:
- 正确关联到文档
- 返回文档名称和页码

### 测试用例 4: 加载提示
**操作**: 发送任何请求
**期望**:
- 前端显示"正在加载上下文..."提示
- 提示消失后显示结果

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模式检测误判 | 用户期望写作却被判为问答 | 增加手动切换按钮（后续迭代） |
| jieba 分词不准确 | 关键词提取失败 | 使用自定义词典 + 优化停用词 |
| 上下文过长 | token 超限 | 保持原有的 max_tokens 限制 |

---

## 项目信息

**工作目录**: `D:\Project Nantianmen\projects\localknowledgebase-word`
**主要文件**:
- `backend/app/api/agent.py`
- `backend/app/services/hierarchical_context.py`
- `frontend/src/components/AICreation/AIChatPanel.tsx`

---

## 完成标准

- [ ] 问答/写作模式正确区分
- [ ] 问答输出简洁，不触发预览
- [ ] 写作输出完整，触发预览
- [ ] 关联查询能正确返回文档信息
- [ ] 前端显示加载提示
- [ ] 所有测试用例通过
