# 🚨 系统性问题：记者系统术语未清理

**发现时间**: 2026-03-07 13:24  
**严重程度**: 🔴 高  
**影响范围**: 全系统

---

## ❌ **问题描述**

当前系统虽然标题改为"智能工艺文件辅助编辑系统"，但代码中仍保留大量"记者/新闻/稿件"相关术语和 prompt，导致：
1. AI 助手显示"🤖 阿西莫夫"（记者系统名字）
2. 提示词还在要求写"新闻稿件"
3. 能读取已删除的数据（可能是指向了错误的数据源）
4. 测试问题与工艺文件无关

---

## 🔍 **发现的问题代码**

### 1. 前端问题

#### `frontend/src/components/AICreation/AIChatPanel.tsx`

**行 795**: 提示文本
```tsx
<p style={{ marginBottom: 8 }}>输入写作主题，AI 将为您撰写深度稿件</p>
```
**应该改为**:
```tsx
<p style={{ marginBottom: 8 }}>输入工艺需求，AI 将为您辅助编辑工艺文件</p>
```

**行 817**: AI 助手名字
```tsx
{msg.role === 'user' ? '你' : '🤖 阿西莫夫'}
```
**应该改为**:
```tsx
{msg.role === 'user' ? '你' : '🤖 工艺助手'}
```

#### `frontend/src/pages/CreationPage.tsx`

**行 501**: 占位符文本
```tsx
placeholder="开始撰写正式稿件..."
```
**应该改为**:
```tsx
placeholder="开始编辑工艺文件..."
```

### 2. 后端问题

#### `backend/app/services/llm_service.py`

**行 37-38**: 函数参数说明
```python
article_type: 稿件类型（快讯/特写/调查报道）
```
**应该改为**:
```python
article_type: 文档类型（工艺规程/操作说明/安全规范）
```

**行 49-67**: 稿件类型定义
```python
article_type_prompts = {
    "news": {
        "name": "新闻快讯",
        "style": "简洁明快，突出时效性和新闻价值，采用倒金字塔结构",
        ...
    },
    "feature": {
        "name": "人物特写",
        ...
    },
    "investigation": {
        "name": "调查报道",
        ...
    }
}
```
**应该改为**:
```python
document_type_prompts = {
    "procedure": {
        "name": "工艺规程",
        "style": "准确规范，步骤清晰，符合工艺文件编写标准",
        ...
    },
    "instruction": {
        "name": "操作说明",
        ...
    },
    "safety": {
        "name": "安全规范",
        ...
    }
}
```

**行 68**: Prompt 模板
```python
prompt = f"""你是一位专业的记者和编辑。请基于以下素材内容，撰写一篇{type_info['name']}。
```
**应该改为**:
```python
prompt = f"""你是一位专业的工艺文件编写专家。请基于以下参考内容，协助编写一份{type_info['name']}。
```

**行 97**: System message
```python
{"role": "system", "content": "你是一位经验丰富的专业新闻记者和编辑，擅长将采访内容整理成高质量的新闻稿件。"}
```
**应该改为**:
```python
{"role": "system", "content": "你是一位经验丰富的专业工艺文件编写专家，擅长根据技术资料编写规范的工艺文件。"}
```

#### `backend/app/models/schemas.py`

**行 16**: 数据模型
```python
article_genre: str = Field(default="新闻报道", description="文章体裁（如：人物专访、深度报道、快讯）")
```
**应该改为**:
```python
document_type: str = Field(default="工艺规程", description="文档类型（如：工艺规程、操作说明、安全规范）")
```

**行 17**:
```python
visual_focus: str = Field(default="", description="稿件的视觉重点描述，指导配图")
```
**应该改为**:
```python
technical_focus: str = Field(default="", description="技术重点描述，指导配图和表格")
```

---

## 📋 **修复优先级**

### 🔴 **高优先级**（立即修复）

1. **AI 助手名字** - `AIChatPanel.tsx`
   - 将 "🤖 阿西莫夫" 改为 "🤖 工艺助手"
   
2. **AI 提示文本** - `AIChatPanel.tsx`
   - 将 "撰写深度稿件" 改为 "辅助编辑工艺文件"

3. **编辑器占位符** - `CreationPage.tsx`
   - 将 "撰写正式稿件" 改为 "编辑工艺文件"

4. **LLM Prompt** - `llm_service.py`
   - 将 "记者" 改为 "工艺文件编写专家"
   - 将 "新闻稿件" 改为 "工艺文件"
   - 将稿件类型改为工艺文件类型

### 🟡 **中优先级**（尽快修复）

5. **数据模型** - `schemas.py`
   - 将 `article_genre` 改为 `document_type`
   - 将 `visual_focus` 改为 `technical_focus`

6. **API 参数** - `creation.py`
   - 将 `style` 参数的值从 "news/feature/investigation" 改为 "procedure/instruction/safety"

### 🟢 **低优先级**（后续优化）

7. **注释和文档**
   - 更新所有注释中的"稿件"相关术语

8. **变量命名**
   - 考虑将 `article_*` 变量改为 `document_*`

---

## 🔧 **修复方案**

### 方案1：逐个文件修复（推荐）

**优点**: 精确控制，易于测试
**缺点**: 耗时较长

**步骤**:
1. 先修复前端提示文本（用户可见）
2. 再修复后端 Prompt（AI 行为）
3. 最后修复数据模型（需要数据库迁移）

### 方案2：批量替换（快速）

**优点**: 快速
**缺点**: 可能遗漏或误改

**命令**:
```bash
# 批量替换（需要仔细检查）
# 前端
sed -i 's/阿西莫夫/工艺助手/g' frontend/src/**/*.tsx
sed -i 's/撰写.*稿件/编辑工艺文件/g' frontend/src/**/*.tsx

# 后端
sed -i 's/记者/工艺文件编写专家/g' backend/app/**/*.py
sed -i 's/新闻/工艺/g' backend/app/**/*.py
```

---

## 🎯 **测试建议**

### 修复后应测试：

1. **AI 助手对话**
   - 打开 AI 面板
   - 确认显示 "🤖 工艺助手"
   - 输入："帮我优化这段工艺描述"
   - 确认 AI 响应符合工艺文件场景

2. **编辑器占位符**
   - 确认显示 "开始编辑工艺文件..."
   
3. **提示文本**
   - 确认显示 "输入工艺需求，AI 将为您辅助编辑工艺文件"

4. **功能测试**
   - 基于 PDF 文档提问
   - AI 应该回答与工艺相关的内容
   - 不应该出现"新闻"、"稿件"等字眼

---

## 📊 **影响评估**

### 受影响的文件：

#### 前端
- `frontend/src/components/AICreation/AIChatPanel.tsx` ✅ 已确认
- `frontend/src/pages/CreationPage.tsx` ✅ 已确认
- `frontend/src/pages/ArticlePage.tsx` ⏳ 待确认
- `frontend/src/pages/ProjectListPage.tsx` ⏳ 待确认

#### 后端
- `backend/app/services/llm_service.py` ✅ 已确认
- `backend/app/models/schemas.py` ✅ 已确认
- `backend/app/api/creation.py` ⏳ 待确认
- `backend/app/models/database.py` ⏳ 待确认

---

## 🚀 **立即行动**

我建议**立即修复高优先级问题**：

1. 修复 AI 助手名字
2. 修复提示文本
3. 修复 LLM Prompt
4. 测试验证

**需要我现在开始修复吗？**

---

**创建时间**: 2026-03-07 13:24  
**负责人**: AI Assistant  
**状态**: 🔴 待修复
