# Implementation Plan: 前后端API接口测试与修复

## Overview
对工艺文件辅助编辑系统的前后端API进行全面测试，识别缺失和不匹配的接口，并进行修复，确保前后端通信正常。

## Requirements Summary
- 测试所有前端调用的API端点
- 对比后端已实现的API路由
- 识别缺失、不匹配、参数不一致的接口
- 修复接口问题，确保系统可正常运行

## Research Findings

### 前端API调用统计
- **服务层API**: 约50个端点
- **组件直接调用**: 约30个端点
- **WebSocket端点**: 1个
- **主要模块**: Agent、创作、风格学习、PDF处理、PDM集成、知识库

### 后端API路由统计
- **路由文件**: 13个
- **API端点**: 89个
- **主要模块**: 创作管理(16)、任务管理(12)、PDF解析(13)、工艺文档(12)

## API不匹配分析

### 1. 完全缺失的后端API（高优先级）

| 前端调用 | 方法 | 状态 | 影响 |
|----------|------|------|------|
| `/api/agent/start-conversation` | POST | ❌ 缺失 | Agent对话无法启动 |
| `/api/agent/reply-question` | POST | ❌ 缺失 | 无法回答问题 |
| `/api/agent/select-plan` | POST | ❌ 缺失 | 无法选择计划 |
| `/api/agent/material-report/{sessionId}` | GET | ❌ 缺失 | 无法获取素材报告 |
| `/api/agent/confirm-materials` | POST | ❌ 缺失 | 无法确认素材 |
| `/api/agent/review-suggestions/{sessionId}` | GET | ❌ 缺失 | 无法查看建议 |
| `/api/agent/apply-suggestions` | POST | ❌ 缺失 | 无法应用建议 |
| `/api/agent/chat` | POST | ❌ 缺失 | 悬浮工具栏聊天不可用 |
| `/api/agent/generate-stream` | POST | ❌ 缺失 | 流式生成不可用 |
| `/api/agent/select-solution` | POST | ❌ 缺失 | 无法选择方案 |
| `/api/agent/generate-article` | POST | ❌ 缺失 | 无法生成文章 |
| `/api/agent/task/{taskId}` | GET | ❌ 缺失 | 无法获取任务状态 |
| `/api/assistant/intent` | POST | ❌ 缺失 | 意图识别不可用 |
| `/api/assistant/suggestions` | GET | ❌ 缺失 | 建议功能不可用 |
| `/api/assistant/generate` | POST | ❌ 缺失 | 助手生成不可用 |

### 2. 风格学习模块完全缺失（中优先级）

| 前端调用 | 方法 | 状态 | 影响 |
|----------|------|------|------|
| `/api/style/articles/upload` | POST | ❌ 缺失 | 风格文章上传不可用 |
| `/api/style/articles` | GET | ❌ 缺失 | 风格文章列表不可用 |
| `/api/style/articles/{id}` | DELETE | ❌ 缺失 | 无法删除风格文章 |
| `/api/style/statistics/{userId}` | GET | ❌ 缺失 | 风格统计不可用 |
| `/api/style/train` | POST | ❌ 缺失 | 风格训练不可用 |
| `/api/style/learn-from-references` | POST | ❌ 缺失 | 参考学习不可用 |
| `/api/style/profiles` | GET/POST | ❌ 缺失 | 风格画像管理不可用 |
| `/api/style/portraits/*` | 多个 | ❌ 缺失 | 风格画像CRUD不可用 |

### 3. 路径不匹配问题

| 前端调用 | 后端实际 | 问题 |
|----------|----------|------|
| `/process-documents/` | `/api/process-documents/` | 前端缺少/api前缀 |
| `/api/process-documents/csv-config` | `/api/process-documents/{docId}/csv-config` | 路径参数缺失 |

### 4. 参数不匹配问题

| 端点 | 前端参数 | 后端参数 | 问题 |
|------|----------|----------|------|
| `POST /api/creation/projects/{id}/materials` | `transcript_ids` | `material_ids` | 参数名已修复 |
| `GET /api/rag/documents` | `page, limit, search, source, status` | `limit, doc_type` | 参数不完全匹配 |

### 5. 后端有但前端未使用的API（低优先级）

这些API可能是预留的或需要前端新增功能：
- `/api/tasks/*` - 任务管理完整API
- `/api/pdf/*` - PDF处理队列API
- `/api/node-documents/*` - 节点文档API
- `/api/documents/*` - 文档上下文API

## Implementation Tasks

### Phase 1: 核心Agent API实现 (优先级最高)

#### 1.1 创建Agent API路由文件
- **Description**: 创建 `backend/app/api/agent.py` 实现Agent相关API
- **Files to create**:
  - `backend/app/api/agent.py`
- **Dependencies**: 无
- **Estimated effort**: 2小时

#### 1.2 实现会话启动API
- **Description**: 实现 `/api/agent/start-conversation` 启动Agent对话
- **Files to modify**:
  - `backend/app/api/agent.py`
  - `backend/main.py` (注册路由)
- **Request Model**:
```python
class StartConversationRequest(BaseModel):
    initial_input: str
    reference_texts: List[str] = []
    business_scenario: str = "general"
    project_id: Optional[int] = None
    user_id: int
```
- **Estimated effort**: 1小时

#### 1.3 实现问题回复API
- **Description**: 实现 `/api/agent/reply-question` 回复Agent问题
- **Request Model**:
```python
class ReplyQuestionRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    selected_option_id: Optional[str] = None
```
- **Estimated effort**: 1小时

#### 1.4 实现计划选择API
- **Description**: 实现 `/api/agent/select-plan` 选择生成计划
- **Request Model**:
```python
class SelectPlanRequest(BaseModel):
    session_id: str
    plan_option_id: str
    custom_plan: Optional[str] = None
```
- **Estimated effort**: 30分钟

#### 1.5 实现素材管理API
- **Description**: 实现素材报告、确认、建议相关API
- **Endpoints**:
  - `GET /api/agent/material-report/{session_id}`
  - `POST /api/agent/confirm-materials`
  - `GET /api/agent/review-suggestions/{session_id}`
  - `POST /api/agent/apply-suggestions`
- **Estimated effort**: 2小时

#### 1.6 实现聊天和流式生成API
- **Description**: 实现聊天和流式响应API
- **Endpoints**:
  - `POST /api/agent/chat`
  - `POST /api/agent/generate-stream` (SSE)
  - `POST /api/agent/reply-question-stream` (SSE)
- **Estimated effort**: 2小时

#### 1.7 实现方案和文章生成API
- **Description**: 实现方案选择和文章生成API
- **Endpoints**:
  - `POST /api/agent/select-solution`
  - `POST /api/agent/generate-article`
  - `GET /api/agent/task/{task_id}`
- **Estimated effort**: 1小时

### Phase 2: Assistant API实现 (中优先级)

#### 2.1 创建Assistant API路由
- **Description**: 创建 `backend/app/api/assistant.py` 实现助手相关API
- **Files to create**:
  - `backend/app/api/assistant.py`
- **Estimated effort**: 30分钟

#### 2.2 实现意图识别和建议API
- **Description**: 实现助手核心功能
- **Endpoints**:
  - `POST /api/assistant/intent` - 意图识别
  - `GET /api/assistant/suggestions` - 获取建议
  - `POST /api/assistant/generate` - 生成内容
- **Estimated effort**: 1.5小时

### Phase 3: 风格学习API实现 (可选)

#### 3.1 创建风格学习路由
- **Description**: 创建 `backend/app/api/style.py` 实现风格学习API
- **Files to create**:
  - `backend/app/api/style.py`
  - `backend/app/models/database.py` (添加风格相关表)
- **Estimated effort**: 1小时

#### 3.2 实现风格文章管理API
- **Endpoints**:
  - `POST /api/style/articles/upload`
  - `GET /api/style/articles`
  - `DELETE /api/style/articles/{id}`
  - `GET /api/style/statistics/{user_id}`
- **Estimated effort**: 2小时

#### 3.3 实现风格训练和画像API
- **Endpoints**:
  - `POST /api/style/train`
  - `POST /api/style/learn-from-references`
  - `GET/POST/PUT/DELETE /api/style/profiles`
  - `GET/POST/PUT /api/style/portraits`
- **Estimated effort**: 3小时

### Phase 4: 路径和参数修复

#### 4.1 修复前端路径前缀问题
- **Description**: 统一前端API路径添加/api前缀
- **Files to modify**:
  - `frontend/src/services/pdfService.ts`
  - `frontend/src/services/csvExportService.ts`
- **Estimated effort**: 30分钟

#### 4.2 修复RAG文档API参数
- **Description**: 对齐前后端RAG文档列表API参数
- **Files to modify**:
  - `backend/app/api/rag.py` (添加page, search, source, status参数)
  - 或修改前端适配后端参数
- **Estimated effort**: 30分钟

### Phase 5: 集成测试

#### 5.1 创建API测试脚本
- **Description**: 创建测试脚本验证所有API端点
- **Files to create**:
  - `backend/tests/test_api_integration.py`
- **Estimated effort**: 1小时

#### 5.2 端到端测试
- **Description**: 运行完整的前后端集成测试
- **Test Cases**:
  - Agent对话流程测试
  - 项目创建和编辑测试
  - 素材管理测试
  - 导出功能测试
- **Estimated effort**: 2小时

## Codebase Integration Points

### Files to Modify

| 文件 | 修改内容 |
|------|----------|
| `backend/main.py` | 注册新的API路由 |
| `backend/app/api/agent.py` | 新建 - Agent API |
| `backend/app/api/assistant.py` | 新建 - Assistant API |
| `backend/app/api/style.py` | 新建 - 风格学习API |
| `frontend/src/services/pdfService.ts` | 修复路径前缀 |
| `frontend/src/services/csvExportService.ts` | 修复路径前缀 |

### New Files to Create

```
backend/app/api/agent.py          # Agent对话API
backend/app/api/assistant.py     # 助手API
backend/app/api/style.py         # 风格学习API
backend/app/models/schemas.py    # 添加新的请求/响应模型
backend/tests/test_api_integration.py  # 集成测试
```

### Existing Patterns to Follow

- API路由使用FastAPI的APIRouter
- 请求/响应使用Pydantic模型
- 数据库操作使用SQLAlchemy ORM
- 日志使用 `app.utils.logger`

## Technical Design

### Agent API架构

```
前端组件
    ↓
/api/agent/*
    ↓
AgentOrchestrator (主控Agent)
    ↓
├── PDFParserAgent
├── RAGRetrieverAgent
├── TerminologyAlignerAgent
├── ComplianceCheckerAgent
└── DocumentGeneratorAgent
```

### API响应格式

```python
# 标准成功响应
{
    "success": true,
    "data": { ... },
    "message": "操作成功"
}

# 错误响应
{
    "success": false,
    "error": "错误类型",
    "message": "错误详情"
}
```

## Testing Strategy

### Unit Tests
- 每个API端点的请求验证
- 响应格式验证
- 错误处理测试

### Integration Tests
- Agent对话完整流程
- 素材管理CRUD
- 项目创建到导出完整链路

### Edge Cases
- 空参数处理
- 无效session_id
- 并发请求处理
- 超时处理

## Success Criteria

- [ ] 所有前端调用的API都有对应的后端实现
- [ ] API路径和参数完全匹配
- [ ] 集成测试全部通过
- [ ] 前端可以正常启动Agent对话
- [ ] 项目创建、编辑、导出功能正常
- [ ] 素材管理功能正常

## Notes and Considerations

### 优先级建议
1. **立即修复**: Agent相关API（Phase 1）- 核心功能
2. **尽快修复**: Assistant API（Phase 2）- 辅助功能
3. **后续实现**: 风格学习API（Phase 3）- 可选功能

### 风险提示
- Agent API涉及复杂的AI逻辑，需要确保LLM服务可用
- 流式API需要正确处理SSE/WebSocket连接
- 风格学习功能可能需要额外的模型训练资源

### 替代方案
如果时间紧迫，可以：
1. 先实现Agent API的Mock版本，返回固定响应
2. 前端添加API调用失败的友好提示
3. 使用后端已有的 `/api/tasks/` API替代部分Agent功能

---
*This plan is ready for execution with `/execute-plan`*
