# Implementation Plan: Orchestrator交互式重设计

## Overview

重新设计Orchestrator的交互模式，从"自动执行"转变为"智能对话"，在关键决策点与用户交互，确保任务执行的准确性和用户满意度。

核心改进：
1. **信息完整性评估**：执行前检查是否有足够信息
2. **预览确认机制**：收集信息后展示预期结果，用户确认后执行
3. **独立Agent调用**：校对/审查Agent可单独使用

## Requirements Summary

### 核心需求
- Orchestrator作为用户与系统的唯一交互入口
- 执行前进行信息完整性评估，识别缺失的关键信息
- 缺失信息时主动与用户确认（文字/图片/文件）
- 收集完信息后给用户预览预期结果
- 用户确认后才开始Agent自动执行
- 校对Agent和审查Agent可独立被调用

### 用户交互流程
```
用户输入
    ↓
意图识别
    ↓
信息完整性评估 ←──┐
    ↓              │
缺信息？──是──→ 向用户确认
    │              │
    否         用户补充（文字/图片/文件）
    ↓              │
预期结果预览       │
    ↓              │
用户确认？──否──→ 返回修改
    │
    是
    ↓
任务分解 + Agent执行
    ↓
返回最终结果
```

## Research Findings

### Best Practices

1. **Conversational AI Design**
   - 主动式对话：系统主动提问而非被动响应
   - 信息收集策略：一次问多个问题，减少来回次数
   - 优先级排序：明确告知哪些信息是必须的，哪些是可选的

2. **User Confirmation Patterns**
   - 预览模式：展示将要执行的操作和预期结果
   - 差异对比：如有修改，展示修改前后对比
   - 进度透明：告知用户当前处于哪个阶段

3. **Agent Orchestration**
   - 单一入口：所有请求通过Orchestrator
   - 灵活调度：支持完整工作流和单独Agent调用
   - 结果聚合：统一的结果格式

### Reference Implementations

1. **ChatGPT的确认机制**：在执行复杂操作前确认用户意图
2. **Manus的信息收集**：主动询问缺失的关键参数
3. **CrewAI的Agent协作**：Agent之间可以独立调用

### Technology Decisions

1. **状态机扩展**：添加新状态支持交互流程
2. **LLM辅助评估**：使用LLM判断信息完整性
3. **消息类型扩展**：支持多种用户输入类型

## Implementation Tasks

### Phase 1: 状态机扩展

#### 1.1 添加新状态
- Description: 在ProcessState枚举中添加信息收集和用户确认相关状态
- Files to modify:
  - `backend/app/agents/orchestrator/state_machine.py`
- Dependencies: None

```python
class ProcessState(str, Enum):
    IDLE = "idle"
    INTENT_RECOGNITION = "intent_recognition"
    INFO_ASSESSMENT = "info_assessment"      # 新增：信息完整性评估
    INFO_COLLECTION = "info_collection"      # 新增：信息收集
    PREVIEW_GENERATION = "preview_generation" # 新增：预览生成
    USER_CONFIRMATION = "user_confirmation"   # 新增：用户确认
    TASK_DECOMPOSITION = "task_decomposition"
    TASK_EXECUTION = "task_execution"
    RESULT_AGGREGATION = "result_aggregation"
    USER_REVIEW = "user_review"
    COMPLETION = "completion"
    ERROR = "error"
    PAUSED = "paused"                        # 新增：暂停（等待用户输入）
```

#### 1.2 添加状态转换规则
- Description: 定义新状态的合法转换路径
- Files to modify:
  - `backend/app/agents/orchestrator/state_machine.py`
- Dependencies: 1.1

### Phase 2: 信息完整性评估器

#### 2.1 创建信息需求模板
- Description: 定义不同任务类型需要的信息
- Files to create:
  - `backend/app/agents/orchestrator/info_requirements.py`
- Dependencies: None

```python
# 信息需求模板示例
INFO_REQUIREMENTS = {
    "calculate_torque": {
        "required": [
            {"name": "screw_spec", "description": "螺钉规格", "example": "M8"},
            {"name": "material", "description": "材料类型", "example": "不锈钢"},
            {"name": "strength_grade", "description": "强度等级", "example": "A2-70"}
        ],
        "optional": [
            {"name": "lubrication", "description": "润滑条件", "default": "干摩擦"}
        ]
    },
    "edit_document": {
        "required": [
            {"name": "target_section", "description": "目标章节"},
            {"name": "edit_content", "description": "编辑内容"}
        ],
        "optional": [
            {"name": "reference_docs", "description": "参考文档"}
        ]
    },
    # ... 更多任务类型
}
```

#### 2.2 实现信息完整性评估器
- Description: 评估当前上下文是否有足够信息
- Files to create:
  - `backend/app/agents/orchestrator/info_assessor.py`
- Dependencies: 2.1

```python
class InfoAssessor:
    """信息完整性评估器"""

    async def assess(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估信息完整性

        Returns:
            {
                "is_complete": bool,
                "missing_info": {
                    "high_priority": [...],
                    "medium_priority": [...],
                    "low_priority": [...]
                },
                "available_info": {...},
                "assessment_confidence": float
            }
        """
```

#### 2.3 集成RAG检索增强评估
- Description: 使用知识库辅助判断信息需求
- Files to modify:
  - `backend/app/agents/orchestrator/info_assessor.py`
- Dependencies: 2.2

### Phase 3: 用户交互管理器

#### 3.1 创建交互消息模型
- Description: 定义系统与用户的交互消息格式
- Files to create:
  - `backend/app/agents/orchestrator/interaction_models.py`
- Dependencies: None

```python
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class InteractionType(str, Enum):
    INFO_REQUEST = "info_request"      # 请求信息
    PREVIEW = "preview"                # 预览结果
    CONFIRMATION = "confirmation"      # 确认请求
    PROGRESS = "progress"              # 进度更新
    RESULT = "result"                  # 最终结果

class MissingInfo(BaseModel):
    """缺失信息项"""
    name: str
    description: str
    example: Optional[str] = None
    impact: str  # 缺失的影响说明
    priority: str  # high/medium/low
    input_type: str = "text"  # text/image/file/folder

class InfoRequestMessage(BaseModel):
    """信息请求消息"""
    interaction_type: InteractionType = InteractionType.INFO_REQUEST
    message: str
    missing_items: List[MissingInfo]
    suggestions: List[str] = []

class PreviewMessage(BaseModel):
    """预览消息（简化版）"""
    interaction_type: InteractionType = InteractionType.PREVIEW
    direction: str              # 处理方向：将怎么处理
    expected_result: str        # 大概结果：会得到什么
    # 例如：
    # direction: "根据您的要求，将编辑工艺文件的切削参数部分"
    # expected_result: "生成更新后的工艺文件，包含新的转速和进给参数"

class ConfirmationMessage(BaseModel):
    """确认消息"""
    interaction_type: InteractionType = InteractionType.CONFIRMATION
    message: str
    options: List[Dict[str, str]]  # [{"label": "确认执行", "value": "confirm"}, ...]
```

#### 3.2 实现交互管理器
- Description: 管理与用户的交互流程
- Files to create:
  - `backend/app/agents/orchestrator/interaction_manager.py`
- Dependencies: 3.1

```python
class InteractionManager:
    """用户交互管理器"""

    def __init__(self, repository=None, dialog_manager=None):
        self.repository = repository
        self.dialog_manager = dialog_manager
        self._pending_interaction: Optional[Dict] = None

    async def request_missing_info(
        self,
        missing_info: Dict[str, List],
        context: Dict[str, Any]
    ) -> InfoRequestMessage:
        """生成信息请求消息"""

    async def generate_preview(
        self,
        intent: Dict[str, Any],
        collected_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> PreviewMessage:
        """生成预览消息"""

    async def process_user_response(
        self,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理用户响应"""

    async def is_awaiting_input(self) -> bool:
        """是否在等待用户输入"""

    def get_pending_interaction(self) -> Optional[Dict]:
        """获取待处理的交互"""
```

#### 3.3 支持多种输入类型
- Description: 处理文字、图片、文件等不同输入
- Files to modify:
  - `backend/app/agents/orchestrator/interaction_manager.py`
- Dependencies: 3.2

### Phase 4: Orchestrator核心重构

#### 4.1 重构process_intent方法
- Description: 添加信息评估和用户确认环节
- Files to modify:
  - `backend/app/agents/orchestrator/orchestrator.py`
- Dependencies: Phase 1, 2, 3

新的process_intent流程：
```python
async def process_intent(
    self,
    user_input: str,
    context: Optional[Dict[str, Any]] = None,
    user_response: Optional[Dict[str, Any]] = None,  # 新增：用户响应
    **kwargs
) -> Dict[str, Any]:
    """
    处理用户输入的工艺意图

    新增交互流程：
    1. 意图识别
    2. 信息完整性评估
    3. 如缺信息 → 返回请求，等待用户补充
    4. 生成预览
    5. 等待用户确认
    6. 执行任务
    """
```

#### 4.2 添加继续对话方法
- Description: 支持用户补充信息后继续
- Files to modify:
  - `backend/app/agents/orchestrator/orchestrator.py`
- Dependencies: 4.1

```python
async def continue_conversation(
    self,
    user_response: Dict[str, Any],
    input_type: str = "text"  # text/image/file/folder
) -> Dict[str, Any]:
    """
    继续对话（用户补充信息后）

    Args:
        user_response: 用户响应内容
        input_type: 输入类型

    Returns:
        下一步的交互消息或执行结果
    """
```

#### 4.3 添加独立Agent调用方法
- Description: 支持单独调用校对/审查Agent
- Files to modify:
  - `backend/app/agents/orchestrator/orchestrator.py`
- Dependencies: 4.1

```python
async def proofread_only(
    self,
    content: str,
    check_type: str = "all",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    仅执行校对（独立调用校对Agent）

    Args:
        content: 待校对内容
        check_type: 检查类型 (terminology/data/format/all)
        context: 执行上下文

    Returns:
        校对结果
    """

async def review_only(
    self,
    content: str,
    check_type: str = "all",
    standards: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    仅执行审查（独立调用审查Agent）

    Args:
        content: 待审查内容
        check_type: 检查类型 (compliance/rationality/risk/all)
        standards: 要检查的标准列表
        context: 执行上下文

    Returns:
        审查结果
    """
```

### Phase 5: API层更新

#### 5.1 更新对话API
- Description: 支持新的交互流程
- Files to modify:
  - `backend/app/api/task.py`
- Dependencies: Phase 4

新增/修改的API端点：
```python
# 继续对话（补充信息）
@router.post("/api/conversation/continue")
async def continue_conversation(request: ContinueRequest):
    """
    继续对话
    - 用户补充文字信息
    - 用户上传图片/文件
    """

# 独立调用校对
@router.post("/api/proofread")
async def proofread_content(request: ProofreadRequest):
    """独立校对接口"""

# 独立调用审查
@router.post("/api/review")
async def review_content(request: ReviewRequest):
    """独立审查接口"""

# 获取当前交互状态
@router.get("/api/conversation/status")
async def get_conversation_status():
    """获取当前对话状态（是否在等待输入等）"""
```

#### 5.2 添加文件上传处理
- Description: 处理用户上传的图片/文件作为信息补充
- Files to modify:
  - `backend/app/api/task.py`
- Dependencies: 5.1

### Phase 6: 预览生成器（简化版）

#### 6.1 创建预览生成器
- Description: 根据任务类型生成简单的方向和结果描述
- Files to create:
  - `backend/app/agents/orchestrator/preview_generator.py`
- Dependencies: None

```python
class PreviewGenerator:
    """预览生成器（简化版）"""

    # 方向模板映射
    DIRECTION_TEMPLATES = {
        "edit_document": "将编辑工艺文件的{target}部分",
        "create_document": "将创建新的{doc_type}工艺文件",
        "calculate": "将计算{calc_type}参数",
        "proofread": "将对内容进行{check_type}检查",
        "review": "将进行{review_type}审查",
    }

    # 结果模板映射
    RESULT_TEMPLATES = {
        "edit_document": "输出修改后的工艺文件内容",
        "create_document": "生成完整的工艺文件",
        "calculate": "输出计算结果和推荐参数",
        "proofread": "输出校对结果和修改建议",
        "review": "输出审查报告和风险提示",
    }

    async def generate(
        self,
        intent: Dict[str, Any],
        collected_info: Dict[str, Any],
    ) -> PreviewMessage:
        """
        生成任务预览（简化版）

        只需要：
        1. direction: 处理方向（将做什么）
        2. expected_result: 预期结果（会得到什么）
        """
        intent_type = intent.get("type", "unknown")

        # 根据意图类型选择模板
        direction = self.DIRECTION_TEMPLATES.get(intent_type, "将处理您的请求")
        result = self.RESULT_TEMPLATES.get(intent_type, "输出处理结果")

        # 填充具体信息
        direction = direction.format(**collected_info)

        return PreviewMessage(
            direction=direction,
            expected_result=result
        )
```

### Phase 7: 测试和验证

#### 7.1 单元测试
- Description: 测试新增组件
- Files to create:
  - `backend/tests/app/agents/orchestrator/test_info_assessor.py`
  - `backend/tests/app/agents/orchestrator/test_interaction_manager.py`
  - `backend/tests/app/agents/orchestrator/test_preview_generator.py`

#### 7.2 集成测试
- Description: 测试完整交互流程
- Files to create:
  - `backend/tests/integration/test_interactive_flow.py`

测试场景：
1. 完整流程：输入 → 缺信息 → 补充 → 预览 → 确认 → 执行
2. 信息齐全：输入 → 预览 → 确认 → 执行
3. 用户取消：输入 → 预览 → 取消
4. 独立校对：直接调用校对Agent
5. 独立审查：直接调用审查Agent

#### 7.3 端到端测试
- Description: 模拟真实用户场景
- Files to create:
  - `backend/tests/e2e/test_user_scenarios.py`

## Codebase Integration Points

### Files to Modify

| File | Changes |
|------|---------|
| `backend/app/agents/orchestrator/state_machine.py` | 添加新状态和转换规则 |
| `backend/app/agents/orchestrator/orchestrator.py` | 重构process_intent，添加新方法 |
| `backend/app/api/task.py` | 添加新API端点 |
| `backend/app/services/__init__.py` | 导出新服务 |

### New Files to Create

| File | Purpose |
|------|---------|
| `backend/app/agents/orchestrator/info_requirements.py` | 信息需求模板定义 |
| `backend/app/agents/orchestrator/info_assessor.py` | 信息完整性评估器 |
| `backend/app/agents/orchestrator/interaction_models.py` | 交互消息模型 |
| `backend/app/agents/orchestrator/interaction_manager.py` | 用户交互管理器 |
| `backend/app/agents/orchestrator/preview_generator.py` | 预览生成器 |
| `backend/tests/...` | 测试文件 |

### Existing Patterns to Follow

1. **Protocol-based设计**：使用Protocol定义接口
2. **Registry模式**：服务注册和发现
3. **异步方法**：所有核心方法使用async/await
4. **结构化日志**：使用get_logger和关键字参数
5. **Pydantic模型**：请求/响应数据验证

## Technical Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ POST /intent │  │POST /continue│  │ POST /proofread │ /review│  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
└─────────┼─────────────────┼───────────────────────┼─────────────────┘
          │                 │                       │
          ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ProcessOrchestrator                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    process_intent()                          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │   │
│  │  │IntentRecog-│→ │InfoAssessor│→ │InteractionManager  │    │   │
│  │  │nizer       │  │            │  │(缺信息→返回等待)    │    │   │
│  │  └────────────┘  └────────────┘  └─────────┬──────────┘    │   │
│  │                                            │                │   │
│  │  ┌──────────────────────────────────────────┼────────────┐ │   │
│  │  │              continue_conversation()     ↓            │ │   │
│  │  │  ┌──────────────┐  ┌─────────────────────────────┐   │ │   │
│  │  │  │PreviewGenera-│→ │ 用户确认? → TaskDecomposer  │   │ │   │
│  │  │  │tor           │  │         ↓                   │   │ │   │
│  │  │  └──────────────┘  │    Agent执行               │   │ │   │
│  │  │                    └─────────────────────────────┘   │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  │                                                              │   │
│  │  ┌──────────────────┐  ┌──────────────────────────────┐    │   │
│  │  │proofread_only()  │  │    review_only()            │    │   │
│  │  │→ ProofreadAgent  │  │    → ReviewAgent            │    │   │
│  │  └──────────────────┘  └──────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Supporting Components                       │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐     │  │
│  │  │StateMachine │  │DialogManager │  │TaskMemoryRepo    │     │  │
│  │  └─────────────┘  └──────────────┘  └──────────────────┘     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Functional Agents                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │WritingAgent  │  │ProofreadAgent│  │    ReviewAgent           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. 用户输入请求
   ↓
2. IntentRecognizer识别意图 → {"type": "calculate_torque", "entities": {...}}
   ↓
3. InfoAssessor评估信息完整性
   ├─ 检查INFO_REQUIREMENTS模板
   ├─ 从上下文提取已有信息
   └─ 生成缺失信息列表
   ↓
4a. 如果缺信息：
    → InteractionManager生成InfoRequestMessage
    → 返回给用户，状态=PAUSED
    → 等待用户调用continue_conversation()

4b. 如果信息完整：
    → PreviewGenerator生成PreviewMessage
    → 返回给用户确认
    → 用户确认后继续
   ↓
5. TaskDecomposer分解任务
   ↓
6. 调度Agent执行
   ↓
7. 聚合结果返回
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/intent` | POST | 提交用户意图 |
| `/api/conversation/continue` | POST | 继续对话（补充信息） |
| `/api/conversation/status` | GET | 获取当前对话状态 |
| `/api/proofread` | POST | 独立调用校对Agent |
| `/api/review` | POST | 独立调用审查Agent |

### Request/Response Models

```python
# 继续对话请求
class ContinueRequest(BaseModel):
    session_id: str
    response_type: str  # text/image/file/folder
    content: Union[str, List[str]]  # 文字内容或文件路径列表

# 预览响应（简化版）
class PreviewResponse(BaseModel):
    session_id: str
    interaction_type: str = "preview"
    direction: str          # 处理方向：将怎么处理
    expected_result: str    # 大概结果：会得到什么
    # 示例：
    # direction: "将根据A2-70不锈钢螺钉连接铝合金的参数，计算M8拧紧力矩"
    # expected_result: "输出推荐的力矩范围值（Nm）和对应的预紧力"

# 信息请求响应
class InfoRequestResponse(BaseModel):
    session_id: str
    interaction_type: str = "info_request"
    message: str
    missing_items: List[MissingInfoItem]
    suggestions: List[str]

# 独立校对请求
class ProofreadRequest(BaseModel):
    content: str
    check_type: str = "all"  # terminology/data/format/all
    auto_fix: bool = False
    target_standard: Optional[str] = None

# 独立审查请求
class ReviewRequest(BaseModel):
    content: str
    check_type: str = "all"  # compliance/rationality/risk/all
    standards: Optional[List[str]] = None
    strict_mode: bool = False
```

## Dependencies and Libraries

无需新增外部依赖，使用现有技术栈：
- FastAPI：API框架
- Pydantic：数据验证
- asyncio：异步处理
- 现有Agent和Tool系统

## Testing Strategy

### Unit Tests
- InfoAssessor：信息完整性评估逻辑
- InteractionManager：交互消息生成
- PreviewGenerator：预览生成

### Integration Tests
- 完整交互流程
- 多轮对话场景
- 状态转换正确性

### Edge Cases
- 用户输入为空
- 信息一直不完整
- 用户取消确认
- 并发会话处理

## Success Criteria

- [ ] 用户输入意图后，系统能正确识别缺失的关键信息
- [ ] 系统能生成清晰的信息请求消息，包含优先级和影响说明
- [ ] 用户补充信息后，系统能正确继续流程
- [ ] 执行前系统能生成任务预览
- [ ] 用户确认后系统才开始执行Agent
- [ ] 校对Agent可独立调用
- [ ] 审查Agent可独立调用
- [ ] 所有测试通过
- [ ] 交互流程符合用户体验预期

## Notes and Considerations

### 重要考虑

1. **用户体验优先**
   - 信息请求要简洁明了
   - 一次问多个问题，减少来回
   - 提供清晰的优先级和影响说明

2. **灵活性**
   - 允许用户跳过可选信息
   - 支持多种输入方式
   - 支持用户随时取消

3. **性能考虑**
   - 信息评估要快速
   - 预览生成不要太耗时
   - 避免重复评估

4. **向后兼容**
   - 现有的process_intent接口保持兼容
   - 新增可选参数而非修改必需参数

### 潜在挑战

1. **信息需求模板维护**：不同任务类型需要持续更新
2. **LLM调用开销**：信息评估可能需要LLM辅助
3. **多轮对话状态管理**：需要可靠的会话状态持久化

### 未来增强

1. **智能信息提取**：从用户上传的图片/文件中自动提取信息
2. **个性化默认值**：根据用户历史设定默认值
3. **批量信息收集**：支持一次上传多个文件批量处理

## 交互示例（简化版）

```
用户: 帮我计算M8螺钉的拧紧力矩

系统: 检测到以下信息缺失：

【高优先级】
1. 螺钉材料（不锈钢/碳钢？）→ 影响摩擦系数，力矩差异±30%
2. 强度等级（4.8/8.8/A2-70？）→ 决定预紧力上限

【中优先级】
3. 被连接件材料（铝合金/钢？）→ 影响啮合设计

您可以：直接回复 / 上传图纸 / 跳过用默认值

用户: 不锈钢A2-70，被连接件铝合金

系统: 收到，任务预览：

📌 方向：计算M8不锈钢(A2-70)螺钉连接铝合金的拧紧力矩
📊 结果：输出推荐的力矩范围值（Nm）和对应预紧力

确认执行？ [确认] [修改]

用户: [确认]

系统: 开始处理...（Agent自动执行）
```

**独立调用示例：**

```
用户: 帮我校对这段工艺描述：[内容...]

系统: 📌 方向：对工艺描述进行术语标准化和格式校验
📊 结果：输出校对结果和修改建议

确认执行？ [确认] [取消]
```

---
*This plan is ready for execution with `/execute-plan`*
