# 🔴 严重问题：AI 无法读取 PDF 文档

**发现时间**: 2026-03-07 13:33  
**严重程度**: 🔴 严重  
**影响范围**: AI 助手核心功能

---

## ❌ **问题描述**

用户在使用 AI 助手时，无法读取上传的 PDF 文档内容，显示 "undefined"。

---

## 🔍 **根本原因**

### 1. **前端没有传递文档信息**
**文件**: `frontend/src/components/AICreation/AIChatPanel.tsx`

**当前代码** (行 512):
```typescript
const response = await fetch('http://localhost:8000/api/agent/generate-stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_input: userInput,
    user_id: 1, 
    project_id: projectId,
    session_id: sessionId
  }),
  signal: controller.signal
})
```

**问题**:
- ❌ 没有传递 `document_id` 或 `pdf_content`
- ❌ 后端无法知道要查询哪个 PDF 文档
- ❌ RAG 系统无法工作

---

### 2. **后端 API 是模拟实现**
**文件**: `backend/app/api/agent.py` (行 575-620)

**当前代码**:
```python
@router.post("/generate-stream")
async def generate_stream(request: GenerateStreamRequest):
    """流式生成内容"""
    logger.info(f"🌊 流式生成: session={request.session_id}")

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'message': '开始生成...'})}\n\n"

        # 模拟流式生成
        content_parts = [
            "# 工艺文件\n\n",
            "## 1. 概述\n\n",
            "本工艺文件描述了...",
            # ...
        ]

        for part in content_parts:
            await asyncio.sleep(0.1)  # 模拟延迟
            yield f"data: {json.dumps({'type': 'content', 'content': part})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'message': '生成完成'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**问题**:
- ❌ 只是返回硬编码的内容
- ❌ 没有调用 RAG 系统
- ❌ 没有查询 PDF 文档
- ❌ 没有使用 LLM

---

### 3. **缺少真正的 RAG 集成**
应该有一个 API 端点：
- 接收用户问题和文档 ID
- 调用 RAG 系统检索相关内容
- 调用 LLM 生成回答
- 流式返回结果

---

## 📋 **修复方案**

### 方案1：修复现有 API（推荐）

#### 步骤1：修改前端请求
**文件**: `frontend/src/components/AICreation/AIChatPanel.tsx`

**应该传递**:
```typescript
body: JSON.stringify({
  user_input: userInput,
  user_id: 1, 
  project_id: projectId,
  session_id: sessionId,
  document_id: currentDocumentId,  // 当前选中的文档 ID
  use_rag: true                    // 启用 RAG 检索
})
```

#### 步骤2：修改后端实现
**文件**: `backend/app/api/agent.py`

**应该实现**:
```python
@router.post("/generate-stream")
async def generate_stream(request: GenerateStreamRequest):
    """流式生成内容 - 基于 RAG"""
    logger.info(f"🌊 流式生成: session={request.session_id}, document_id={request.document_id}")

    async def generate():
        try:
            # 1. 从 RAG 系统检索相关内容
            if request.document_id:
                from app.services.rag_service import rag_service
                
                relevant_chunks = await rag_service.search(
                    query=request.user_input,
                    document_id=request.document_id,
                    top_k=5
                )
                
                context = "\n\n".join([chunk['content'] for chunk in relevant_chunks])
            else:
                context = ""

            # 2. 调用 LLM 生成回答
            from app.services.llm_service import QwenLLMService
            llm_service = QwenLLMService()
            
            prompt = f"""你是一位专业的工艺文件编写专家。请基于以下参考内容回答用户问题。

【参考内容】
{context}

【用户问题】
{request.user_input}

【要求】
- 如果参考内容中有相关信息，请基于参考内容回答
- 如果参考内容中没有相关信息，请明确说明
- 回答要专业、准确、简洁
"""
            
            # 3. 流式生成
            yield f"data: {json.dumps({'type': 'start', 'message': '正在检索文档...'})}\n\n"
            
            response = await llm_service.stream_chat(
                messages=[
                    {"role": "system", "content": "你是一位经验丰富的专业工艺文件编写专家。"},
                    {"role": "user", "content": prompt}
                ]
            )
            
            async for chunk in response:
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete', 'message': '生成完成'})}\n\n"
            
        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

#### 步骤3：修改请求模型
**文件**: `backend/app/api/agent.py`

```python
class GenerateStreamRequest(BaseModel):
    """流式生成请求"""
    session_id: Optional[str] = Field(None, description="会话ID")
    user_input: str = Field(..., description="用户输入")
    user_id: int = Field(..., description="用户ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    document_id: Optional[str] = Field(None, description="文档ID")
    use_rag: bool = Field(default=True, description="是否使用RAG")
```

---

### 方案2：创建新的 RAG API

#### 新建 API 端点
**文件**: `backend/app/api/rag.py` (新建)

```python
@router.post("/chat-with-document")
async def chat_with_document(request: ChatWithDocumentRequest):
    """基于文档的对话"""
    # 实现类似方案1的逻辑
    pass
```

---

## 🎯 **推荐行动**

### 立即修复（高优先级）
1. **修改后端 `/generate-stream` API**
   - 实现 RAG 检索
   - 调用 LLM
   - 流式返回

2. **修改前端请求**
   - 传递 `document_id`
   - 传递 `use_rag: true`

3. **测试验证**
   - 上传 PDF 文档
   - 提问："这个工艺的关键参数是什么？"
   - 确认 AI 基于 PDF 内容回答

---

## 📊 **影响评估**

### 当前状态
- ❌ AI 助手完全不可用（无法读取 PDF）
- ❌ 用户看到 "undefined"
- ❌ 核心功能失效

### 修复后
- ✅ AI 可以基于 PDF 内容回答
- ✅ RAG 系统正常工作
- ✅ 用户体验良好

---

## 🚀 **下一步**

**我建议立即修复方案1**，因为：
1. 前端已经调用了 `/generate-stream` API
2. 只需要修改后端实现
3. 添加 `document_id` 参数传递

**需要我现在开始修复吗？**

---

**创建时间**: 2026-03-07 13:33  
**负责人**: AI Assistant  
**状态**: 🔴 待修复
