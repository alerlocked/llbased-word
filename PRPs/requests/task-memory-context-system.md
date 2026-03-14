# Implementation Plan: 任务记忆与上下文管理系统

## Overview

基于Manus式上下文注入架构，实现任务级记忆系统和文件系统上下文管理。核心设计理念：
- **文件系统作为主存储**：零依赖，兼容Windows 7/麒麟
- **Repository抽象层**：单机用JSON，部署时无成本切换SQLite
- **上下文注入**：直接把相关文件塞进LLM上下文，无需向量数据库

## Requirements Summary

- 任务级独立记忆空间（每个任务独立的JSON文件目录）
- 任务命名规则：`{任务名}_{时间戳}`，如 `电缆装配编辑_20260224_143000`
- 统一的Repository抽象接口（支持JSON/SQLite双实现）
- 文件系统上下文管理器（从exports_vlm_full读取解析后的PDF数据）
- 与现有Orchestrator集成
- 支持单机调试（JSON文件）和部署（SQLite）的无缝切换

## Research Findings

### Best Practices

1. **Repository模式**：领域驱动设计中的标准模式，将数据访问逻辑与业务逻辑分离
2. **依赖注入**：通过构造函数注入Repository实现，方便测试和切换
3. **Pydantic模型**：用于数据验证和序列化，与现有代码风格一致
4. **语义化命名**：任务名+时间戳，便于人工识别和检索

### Reference Implementations

- 现有代码：`backend/app/agents/orchestrator/dialog_manager.py` - 内存中的对话管理
- 现有代码：`backend/app/agents/orchestrator/state_machine.py` - 状态机实现
- 现有代码：`backend/app/config.py` - 配置管理模式
- 数据源：`data/exports_vlm_full/` - PDF解析结果

### Technology Decisions

| 决策 | 选择 | 原因 |
|------|------|------|
| 存储格式 | JSON文件 | 调试友好，可直接打开查看 |
| 抽象层 | Protocol类 | Python 3.8+原生支持，轻量 |
| 数据验证 | Pydantic v2 | 与现有代码一致 |
| 上下文格式 | Markdown | LLM友好，表格可读性好 |
| 任务命名 | 任务名_时间戳 | 语义清晰，便于人工识别 |

## Implementation Tasks

### Phase 1: 基础设施层（Repository抽象）

#### Task 1.1: 定义Repository接口协议
- Description: 创建Repository抽象协议，定义所有记忆操作的接口
- Files to create:
  - `backend/app/repositories/__init__.py`
  - `backend/app/repositories/protocols.py`
- Dependencies: 无
- 接口方法:
  - `create_task(task_name, task_type, source_docs) -> task_id`
  - `get_meta(task_id) -> TaskMeta`
  - `update_meta(task_id, updates)`
  - `get_state(task_id) -> TaskState`
  - `update_state(task_id, new_state, pending_action)`
  - `get_messages(task_id, limit) -> List[Message]`
  - `add_message(task_id, role, content, metadata)`
  - `get_decisions(task_id) -> List[Decision]`
  - `add_decision(task_id, decision)`
  - `get_context(task_id) -> str` (构建完整上下文)
  - `list_tasks() -> List[TaskMeta]` (列出所有任务)

#### Task 1.2: 实现JsonFileRepository
- Description: 基于JSON文件的Repository实现，用于单机调试
- Files to create:
  - `backend/app/repositories/json_repository.py`
- Dependencies: Task 1.1
- 功能:
  - 文件系统目录结构管理
  - JSON读写封装
  - 自动创建任务目录和初始化文件
  - 任务命名：`{task_name}_{YYYYMMDD_HHMMSS}`

#### Task 1.3: 实现SQLiteRepository（骨架）
- Description: SQLite实现的骨架代码，部署时填充
- Files to create:
  - `backend/app/repositories/sqlite_repository.py`
- Dependencies: Task 1.1
- 功能:
  - 数据库表结构定义
  - SQL操作封装
  - 事务支持
  - 初期为NotImplementedError，后续填充

#### Task 1.4: Repository工厂和配置
- Description: 根据配置选择Repository实现
- Files to create:
  - `backend/app/repositories/factory.py`
- Files to modify:
  - `backend/app/config.py` - 添加REPOSITORY_TYPE配置
- Dependencies: Task 1.2, Task 1.3
- 配置项:
  - `REPOSITORY_TYPE: str = "json"` # json | sqlite
  - `TASK_DATA_DIR: Path` # 任务数据存储目录

### Phase 2: 数据模型定义

#### Task 2.1: 任务记忆数据模型
- Description: 定义任务记忆相关的Pydantic模型
- Files to create:
  - `backend/app/models/task_memory.py`
- Dependencies: 无
- 模型定义:
  - `TaskMeta` - 任务元数据
  - `TaskState` - 状态机状态
  - `Message` - 对话消息
  - `Decision` - 决策记录
  - `TaskContext` - 上下文缓存

#### Task 2.2: 更新现有models/__init__.py
- Description: 导出新模型
- Files to modify:
  - `backend/app/models/__init__.py`
- Dependencies: Task 2.1

### Phase 3: 上下文管理器

#### Task 3.1: 文件系统上下文管理器
- Description: 从exports_vlm_full读取PDF解析结果，构建LLM上下文
- Files to create:
  - `backend/app/services/context_manager.py`
- Dependencies: 无
- 功能:
  - `get_document_list()` - 获取已解析文档列表
  - `get_document_tables(doc_name)` - 获取文档的所有表格
  - `get_document_markdown(doc_name)` - 获取文档的Markdown表示
  - `search_by_caption(doc_name, caption)` - 按表格标题搜索
  - `build_document_context(doc_names)` - 构建多文档上下文

#### Task 3.2: 上下文构建器
- Description: 组装完整任务上下文（任务信息+对话历史+源文档）
- Files to create:
  - `backend/app/services/context_builder.py`
- Dependencies: Task 3.1, Task 1.2
- 功能:
  - 读取任务meta/state/conversation/decisions
  - 加载关联的源文档内容
  - 格式化为LLM友好的Markdown
  - 支持上下文长度限制（截断策略）

### Phase 4: 集成到Orchestrator

#### Task 4.1: 重构DialogManager使用Repository
- Description: 修改现有DialogManager，底层使用Repository
- Files to modify:
  - `backend/app/agents/orchestrator/dialog_manager.py`
- Dependencies: Task 1.2
- 改动:
  - 注入Repository依赖
  - 对话历史持久化到Repository
  - 保留内存缓存以提高性能

#### Task 4.2: 重构ProcessStateMachine使用Repository
- Description: 修改状态机，状态持久化到Repository
- Files to modify:
  - `backend/app/agents/orchestrator/state_machine.py`
- Dependencies: Task 1.2
- 改动:
  - 状态变更时同步到Repository
  - 支持从Repository恢复状态

#### Task 4.3: 更新Orchestrator主类
- Description: 集成Repository和ContextBuilder
- Files to modify:
  - `backend/app/agents/orchestrator/orchestrator.py`
- Dependencies: Task 4.1, Task 4.2, Task 3.2
- 改动:
  - 注入Repository
  - process_intent开始时加载/创建任务
  - 推理前调用ContextBuilder构建上下文
  - 推理后更新Repository

### Phase 5: API层改造

#### Task 5.1: 任务管理API
- Description: 新增任务相关的API端点
- Files to modify:
  - `backend/app/api/agent.py` 或新建 `backend/app/api/task.py`
- Dependencies: Task 4.3
- 端点:
  - `POST /api/tasks` - 创建新任务
  - `GET /api/tasks` - 获取任务列表
  - `GET /api/tasks/{task_id}` - 获取任务信息
  - `GET /api/tasks/{task_id}/context` - 获取任务上下文（调试用）
  - `GET /api/tasks/{task_id}/history` - 获取对话历史
  - `POST /api/tasks/{task_id}/messages` - 发送消息
  - `GET /api/documents` - 获取可用文档列表
  - `GET /api/documents/{doc_name}/tables` - 获取文档表格

#### Task 5.2: WebSocket实时通信（可选）
- Description: 支持流式响应和状态推送
- Files to create:
  - `backend/app/api/websocket.py`
- Dependencies: Task 5.1
- 功能:
  - 任务状态变更推送
  - 流式响应

### Phase 6: 测试与验证

#### Task 6.1: Repository单元测试
- Description: 测试JsonFileRepository的各项操作
- Files to create:
  - `backend/tests/repositories/test_json_repository.py`
- Dependencies: Task 1.2
- 测试用例:
  - 创建任务
  - 读写meta/state/messages/decisions
  - 上下文构建
  - 任务列表查询

#### Task 6.2: 集成测试
- Description: 端到端测试任务流程
- Files to create:
  - `backend/tests/integration/test_task_flow.py`
- Dependencies: Task 4.3
- 测试场景:
  - 创建任务 → 发送消息 → 获取响应 → 查看历史
  - 多轮对话上下文保持
  - 源文档加载

#### Task 6.3: 功能验证
- Description: 验证整体功能可用性
- Files to create:
  - `backend/tests/validation/test_e2e.py`
- Dependencies: Task 4.3
- 测试场景:
  - 完整工艺编辑流程
  - 上下文构建延迟
  - 文档加载正确性

## Codebase Integration Points

### Files to Modify

| 文件 | 改动说明 |
|------|----------|
| `backend/app/config.py` | 添加REPOSITORY_TYPE、TASK_DATA_DIR配置 |
| `backend/app/agents/orchestrator/dialog_manager.py` | 底层使用Repository |
| `backend/app/agents/orchestrator/state_machine.py` | 状态持久化到Repository |
| `backend/app/agents/orchestrator/orchestrator.py` | 集成Repository和ContextBuilder |
| `backend/app/models/__init__.py` | 导出新模型 |

### New Files to Create

| 文件 | 用途 |
|------|------|
| `backend/app/repositories/__init__.py` | 模块初始化 |
| `backend/app/repositories/protocols.py` | Repository接口协议 |
| `backend/app/repositories/json_repository.py` | JSON文件实现 |
| `backend/app/repositories/sqlite_repository.py` | SQLite实现（骨架） |
| `backend/app/repositories/factory.py` | 工厂函数 |
| `backend/app/models/task_memory.py` | 数据模型 |
| `backend/app/services/context_manager.py` | 文档上下文管理 |
| `backend/app/services/context_builder.py` | 上下文构建器 |
| `backend/app/api/task.py` | 任务API（可选） |
| `backend/tests/repositories/test_json_repository.py` | 单元测试 |
| `backend/tests/integration/test_task_flow.py` | 集成测试 |

### Existing Patterns to Follow

1. **日志规范**：使用`from app.shared.logging import get_logger`，关键字参数传参
2. **Pydantic模型**：使用Pydantic v2语法，`BaseModel`继承
3. **异步方法**：所有IO操作使用async/await
4. **依赖注入**：通过构造函数注入依赖
5. **配置管理**：使用Settings类，支持.env文件

## Technical Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                     │
│              /api/tasks, /api/documents                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator (LangGraph)                   │
│     意图识别 → 任务分解 → Agent调度 → 结果聚合 → 状态推进     │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ TaskMemoryRepo  │  │ ContextBuilder  │  │   子Agent集群    │
│   (抽象接口)     │  │  (上下文构建)    │  │                 │
└────────┬────────┘  └────────┬────────┘  └─────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│JsonRepository   │  │ContextManager   │
│ (调试用JSON)     │  │(exports_vlm_full)│
├─────────────────┤  └─────────────────┘
│SQLiteRepository │
│ (部署用数据库)   │
└─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                      File System                             │
│  data/tasks/电缆装配编辑_20260224_143000/                    │
│  ├── meta.json        ├── conversation.json                  │
│  ├── state.json       ├── decisions.json                     │
│  └── artifacts/                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
用户请求
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. API接收请求，提取/创建 task_id                            │
│    POST /api/tasks  → 创建 "电缆装配编辑_20260224_143000"    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Orchestrator.process_intent(user_input, task_id)         │
│    - 从Repository加载任务状态                                 │
│    - 检查状态机是否允许当前操作                                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ContextBuilder.build_context(task_id)                    │
│    - 从Repository读取meta/state/messages/decisions           │
│    - 从ContextManager加载源文档内容                          │
│    - 拼接为完整上下文字符串                                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. LLM推理                                                   │
│    - System Prompt = 任务上下文 + 系统指令                   │
│    - User Message = 用户输入                                 │
│    - 调用DeepSeek-R1或其他模型                                │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 更新任务记忆                                              │
│    - add_message() 记录对话                                   │
│    - update_state() 推进状态                                  │
│    - add_decision() 记录关键决策（如有）                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. 返回响应给用户                                            │
└─────────────────────────────────────────────────────────────┘
```

### Data Models

```
TaskMeta:
  - task_id: str           # 电缆装配编辑_20260224_143000
  - task_name: str         # 电缆装配编辑
  - type: str              # craft_document_edit
  - created_at: datetime
  - updated_at: datetime
  - status: str            # pending/in_progress/completed
  - source_documents: List[str]
  - tags: List[str]

TaskState:
  - current_state: str     # init/editing/review/completed
  - state_history: List[StateTransition]
  - pending_action: Optional[dict]

Message:
  - role: str              # user/assistant
  - content: str
  - timestamp: datetime
  - metadata: Optional[dict]

Decision:
  - id: str
  - type: str              # tool_selection/method_choice
  - context: str
  - options: List[str]
  - selected: str
  - reason: str
  - user_confirmed: bool
```

### Directory Structure

```
data/
├── tasks/                                      # 任务记忆仓库
│   ├── 电缆装配编辑_20260224_143000/           # 任务目录
│   │   ├── meta.json                          # 任务元数据
│   │   ├── state.json                         # 状态机状态
│   │   ├── conversation.json                  # 对话历史
│   │   ├── decisions.json                     # 决策记录
│   │   └── artifacts/                         # 生成的文件
│   │       └── draft_v1.docx
│   │
│   └── 材料定额计算_20260224_150000/
│       └── ...
│
├── knowledge/                                  # 全局知识（跨任务共享）
│   ├── terminology.json                       # 工艺术语库
│   └── templates/                             # 文档模板
│
└── exports_vlm_full/                          # PDF解析结果（只读）
    └── ...
```

### API Endpoints

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/tasks` | POST | 创建新任务（body: {name, type, source_docs}） |
| `/api/tasks` | GET | 获取任务列表 |
| `/api/tasks/{task_id}` | GET | 获取任务信息 |
| `/api/tasks/{task_id}/messages` | GET | 获取对话历史 |
| `/api/tasks/{task_id}/messages` | POST | 发送消息 |
| `/api/tasks/{task_id}/decisions` | GET | 获取决策记录 |
| `/api/tasks/{task_id}/context` | GET | 获取完整上下文（调试） |
| `/api/documents` | GET | 获取可用文档列表 |
| `/api/documents/{doc_name}/tables` | GET | 获取文档表格 |
| `/api/documents/{doc_name}/markdown` | GET | 获取文档Markdown |

## Dependencies and Libraries

| 库 | 版本 | 用途 |
|-----|------|------|
| pydantic | ^2.0.0 | 数据验证（已有） |
| aiofiles | ^23.0.0 | 异步文件操作 |

## Testing Strategy

### Unit Tests
- `test_json_repository.py`: Repository CRUD操作
- `test_context_manager.py`: 文档加载和格式化
- `test_context_builder.py`: 上下文拼接

### Integration Tests
- `test_task_flow.py`: 完整任务流程
- `test_orchestrator_integration.py`: Orchestrator与Repository集成

### Edge Cases
- 任务不存在时的处理
- 文件损坏时的恢复
- 上下文超长时的截断

## Success Criteria

- [ ] Repository抽象层完成，JsonFileRepository可用
- [ ] 任务命名符合规范：{任务名}_{时间戳}
- [ ] 任务创建、状态管理、对话历史持久化正常
- [ ] ContextManager能从exports_vlm_full加载文档
- [ ] ContextBuilder能构建完整上下文
- [ ] Orchestrator集成完成，process_intent使用Repository
- [ ] API端点可用，可通过HTTP创建任务和发送消息
- [ ] 单元测试覆盖率>80%
- [ ] 配置切换REPOSITORY_TYPE可切换存储后端

## Notes and Considerations

### 潜在风险

1. **上下文长度**：大量文档可能超出LLM上下文窗口，需要截断策略
2. **迁移兼容性**：需要考虑现有会话数据的迁移

### 后续增强

1. **SQLiteRepository完整实现**：部署时填充
2. **上下文压缩**：对历史对话进行摘要压缩
3. **向量索引**：可选的语义检索层
4. **WebSocket推送**：实时状态更新

### 与现有代码的兼容性

- DialogManager保留内存缓存层，Repository作为持久化后端
- ProcessStateMachine的VALID_TRANSITIONS规则保持不变
- 现有API端点保持兼容，新增任务管理端点

---
*This plan is ready for execution with `/execute-plan`*
