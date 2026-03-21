# PRP: 修复AI助手无响应问题

## 问题现象

**测试场景**：
- 前端发送 `POST /api/agent/generate-stream`
- 请求内容：`{"prompt": "测试AI助手响应"}`
- 后端接收请求（01:15:04），返回200（0.002秒）
- **没有后续处理日志**
- 前端无AI生成内容

**测试时间**：2026-03-20 01:15
**测试项目**：项目ID=2 "测试工艺文件项目"
**已上传文件**：全单电缆装配规程.pdf

---

## 根因分析

### 1. 后端日志分析

```log
[2026-03-20 01:15:04] 📥 [请求] POST /api/agent/generate-stream
[2026-03-20 01:15:04] 📥 [请求] Content-Type: application/json
[2026-03-20 01:15:04] 🌊 流式生成: session=None
[2026-03-20 01:15:04] 📤 [响应] POST /api/agent/generate-stream - 200 (0.002s)
```

**问题**：
- 请求已接收 ✅
- 返回200成功 ✅
- **但响应时间只有0.002秒** - 太快了，不可能完成AI生成
- **没有后续日志** - Agent模块、LLM调用、知识库检索都没有日志

### 2. 可能原因

```yaml
1. Agent模块未正确调用:
  - generate_stream 端点可能直接返回成功，没有实际调用Agent

2. LLM配置问题:
  - API Key 未配置或配置错误
  - 模型配置错误
  - 网络连接问题

3. 知识库检索失败:
  - 文件未正确解析
  - 向量检索失败
  - RAG模块未初始化

4. 流式响应未建立:
  - 前端未正确建立 SSE 连接
  - 后端未正确实现流式输出
```

---

## 修复方案

### Phase 1: 添加详细日志（诊断）

**目标**：定位问题具体位置

**需要修改的文件**：
- `backend/app/api/agent.py` - generate_stream 端点

**需要添加的日志**：
```python
# 1. 请求接收日志
logger.info(f"[AI助手] 收到请求: prompt={prompt[:50]}...")

# 2. Agent初始化日志
logger.info(f"[AI助手] 初始化Agent: workflow={workflow}")

# 3. 知识库检索日志
logger.info(f"[AI助手] 开始检索知识库: folder_ids={folder_ids}")
logger.info(f"[AI助手] 检索结果: {len(results)} 条相关内容")

# 4. LLM调用日志
logger.info(f"[AI助手] 调用LLM: model={model}, prompt_length={len(prompt)}")
logger.info(f"[AI助手] LLM响应: 第一块已生成")

# 5. 流式输出日志
logger.info(f"[AI助手] 开始流式输出...")
```

### Phase 2: 检查配置

**需要检查的配置**：
```yaml
1. LLM配置:
  - backend/app/config.py - DEEPSEEK_API_KEY
  - 确认API Key已配置
  - 确认模型名称正确

2. 知识库配置:
  - 确认文件已上传
  - 确认文件已解析
  - 确认向量索引已建立

3. RAG配置:
  - 确认RAG模块已初始化
  - 确认检索器可用
```

### Phase 3: 修复核心逻辑

**根据诊断结果修复**：
- 如果是Agent未调用 → 修复调用逻辑
- 如果是LLM配置错误 → 修复配置
- 如果是知识库问题 → 修复检索逻辑
- 如果是流式响应问题 → 修复SSE实现

---

## 测试环境

```yaml
项目路径: D:\Project Nantianmen\projects\localknowledgebase-word
后端: http://127.0.0.1:8000
前端: http://localhost:3000
测试项目ID: 2
测试文件: 全单电缆装配规程.pdf
```

## 验证步骤

### 1. 启动服务
```bash
cd D:\Project Nantianmen\projects\localknowledgebase-word\backend
python main.py

cd D:\Project Nantianmen\projects\localknowledgebase-word\frontend
npm run dev
```

### 2. 测试AI助手
1. 打开 http://localhost:3000/?project=2
2. 点击 robot 按钮
3. 输入："测试AI助手响应"
4. 点击"生成"按钮
5. 观察后端日志，确认有完整的处理流程
6. 观察前端，确认有AI生成内容

### 3. 检查日志
```bash
# 应该看到完整的日志链：
[AI助手] 收到请求
[AI助手] 初始化Agent
[AI助手] 开始检索知识库
[AI助手] 检索结果
[AI助手] 调用LLM
[AI助手] LLM响应
[AI助手] 开始流式输出
```

---

## 成功标准

```yaml
1. 后端日志:
  - 有完整的处理流程日志
  - 有LLM调用日志
  - 有知识库检索日志

2. 前端显示:
  - AI助手返回生成内容
  - 内容与测试文件相关

3. 响应时间:
  - 首块响应 < 5秒
  - 完整响应 < 30秒
```

---

## 优先级

**P0 - 最高优先级**

AI助手是核心功能，必须修复。

---

## 关键文件

```yaml
后端:
  - backend/app/api/agent.py - AI助手API端点
  - backend/app/services/agent_service.py - Agent服务
  - backend/app/services/rag_service.py - RAG服务
  - backend/app/config.py - 配置文件

前端:
  - frontend/src/components/AIAssistant/ - AI助手组件
```

---

## 修复记录

**修复时间**: 2026-03-20 10:37

**根因**:
后端 `generate_stream` 端点返回的 SSE 数据格式与前端期望的格式不匹配。

- **后端返回**: `type: 'content'`, `type: 'complete'`
- **前端期望**: `type: 'progress'`, `type: 'result'`, `type: 'error'`

前端没有处理 `type: 'content'` 类型的数据，导致 AI 响应内容被忽略。

**修复方案**:
修改 `backend/app/api/agent.py` 中的 `generate_stream` 函数：
1. 将流式内容输出改为 `type: 'progress'` 格式
2. 最终结果使用 `type: 'result'` 格式
3. 错误信息使用 `type: 'error'` 格式

**验证结果**:
```bash
# 测试命令
curl -X POST http://localhost:8000/api/agent/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"user_input": "test"}'

# 返回结果（已修复）
data: {"type": "progress", "node": "planner", "message": "正在分析您的需求..."}
data: {"type": "progress", "node": "writer", "message": "正在生成回复...", "data": {"content_preview": ""}}
data: {"type": "result", "content": "您好！感谢您的输入..."}
```

**状态**: ✅ 已修复
