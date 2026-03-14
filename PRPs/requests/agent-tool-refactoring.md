# Implementation Plan: Agent/Tool 架构重构

## Overview

将当前的Agent/Tool架构重构为三层模块化架构，实现：
1. **Orchestrator层** - 主控，接收用户意图，协调Agent协作
2. **功能Agent层** - WritingAgent(撰写)、ProofreadAgent(校对)、ReviewAgent(审查)
3. **Tool层** - 底层工具，单一职责，可插拔

同时将PDF解析独立为后台服务，不在主流程中。

## Requirements Summary

- 模块化设计：Agent和Tool都支持动态注册和发现
- 可扩展性：新增Agent或Tool无需修改核心代码
- 标准接口：使用Protocol定义Agent和Tool的接口规范
- 三层架构：Orchestrator → 功能Agent → Tool
- PDF解析后台化：监听文件夹，自动解析

## Research Findings

### Best Practices

1. **Protocol vs ABC**
   - 使用 `typing.Protocol` 而非 `abc.ABC`，更符合Python鸭子类型
   - Protocol支持结构化子类型，无需显式继承
   - 配合 `@runtime_checkable` 支持运行时检查

2. **Registry Pattern**
   - 使用 `Dict[str, Type]` 实现组件注册表
   - 支持按名称/类型查找组件
   - 支持装饰器自动注册

3. **Plugin Architecture**
   - 工厂模式创建组件实例
   - 依赖注入解耦组件
   - 配置驱动行为

### Reference Implementations

- [LangChain Agent架构](https://developer.baidu.com/article/detail.html?id=5534845) - Tool插件化设计
- [Python Protocol插件系统](https://baijiahao.baidu.com/s?id=1831714312074196494) - 结构化子类型
- [插件化架构落地](https://wenku.csdn.net/column/4jgjek4zk) - PluginContainer注册表

### Technology Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 接口定义 | `Protocol` | 鸭子类型友好，无需继承 |
| 注册机制 | 装饰器+字典 | 简单高效，自动发现 |
| 依赖注入 | 构造函数注入 | 显式依赖，易于测试 |
| 配置管理 | 现有config系统 | 保持一致性 |

## Implementation Tasks

### Phase 1: 基础架构 - 接口和注册系统

#### 1.1 定义Tool协议
- **Description**: 创建Tool的Protocol接口，定义标准方法
- **Files to create**:
  - `backend/app/agents/core/protocols.py`
- **Dependencies**: 无
- **Code**:
```python
from typing import Protocol, Any, Dict, Optional, runtime_checkable

@runtime_checkable
class ToolProtocol(Protocol):
    """Tool标准接口"""
    name: str
    description: str

    async def execute(self, input_data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """执行工具，返回标准格式结果"""
        ...
```

#### 1.2 定义Agent协议
- **Description**: 创建Agent的Protocol接口
- **Files to create**:
  - `backend/app/agents/core/protocols.py` (扩展)
- **Dependencies**: 1.1
- **Code**:
```python
@runtime_checkable
class AgentProtocol(Protocol):
    """Agent标准接口"""
    name: str
    description: str
    tools: List[str]  # 依赖的Tool名称列表

    async def process(self, task: Dict[str, Any], context: Optional[Dict] = None) -> Dict[str, Any]:
        """处理任务，返回结果"""
        ...
```

#### 1.3 实现Tool注册表
- **Description**: 创建ToolRegistry，支持装饰器注册和查找
- **Files to create**:
  - `backend/app/agents/core/registry.py`
- **Dependencies**: 1.1
- **Code**:
```python
class ToolRegistry:
    """Tool注册表"""
    _instance = None
    _tools: Dict[str, Type[ToolProtocol]] = {}

    @classmethod
    def register(cls, name: str):
        """装饰器：注册Tool"""
        def decorator(tool_class: Type[ToolProtocol]):
            cls._tools[name] = tool_class
            return tool_class
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[Type[ToolProtocol]]:
        return cls._tools.get(name)

    @classmethod
    def create(cls, name: str, config: Optional[Dict] = None) -> Optional[ToolProtocol]:
        tool_class = cls.get(name)
        if tool_class:
            return tool_class(config)
        return None
```

#### 1.4 实现Agent注册表
- **Description**: 创建AgentRegistry，与ToolRegistry类似
- **Files to create**:
  - `backend/app/agents/core/registry.py` (扩展)
- **Dependencies**: 1.2
- **Code**: 与ToolRegistry类似

#### 1.5 创建core模块初始化
- **Description**: 整合core模块导出
- **Files to create**:
  - `backend/app/agents/core/__init__.py`
- **Dependencies**: 1.1-1.4

---

### Phase 2: Tool层重构

#### 2.1 重构RAGRetriever Tool
- **Description**: 将vector_store封装为标准Tool
- **Files to modify/create**:
  - `backend/app/tools/rag_retriever.py` (新建，从vector_store提取)
- **Dependencies**: 1.1, 1.3
- **Code**:
```python
from app.agents.core import ToolProtocol, ToolRegistry

@ToolRegistry.register("rag_retriever")
class RAGRetriever:
    name = "rag_retriever"
    description = "工艺知识检索工具"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.vector_store = VectorStore(config)

    async def execute(self, input_data: str, context: Optional[Dict] = None) -> Dict:
        # 检索逻辑
        ...
```

#### 2.2 重构TerminologyMapper Tool
- **Description**: 术语映射工具，单一职责
- **Files to modify/create**:
  - `backend/app/tools/terminology_tool.py`
- **Dependencies**: 1.1, 1.3

#### 2.3 重构ComplianceChecker Tool
- **Description**: 合规检查工具
- **Files to modify/create**:
  - `backend/app/tools/compliance_tool.py`
- **Dependencies**: 1.1, 1.3

#### 2.4 重构DocumentGenerator Tool
- **Description**: 文档生成工具
- **Files to modify/create**:
  - `backend/app/tools/document_tool.py`
- **Dependencies**: 1.1, 1.3

#### 2.5 创建Tool自动发现
- **Description**: 扫描tools目录，自动注册所有Tool
- **Files to modify/create**:
  - `backend/app/tools/__init__.py`
- **Dependencies**: 2.1-2.4
- **Code**:
```python
def discover_tools():
    """自动发现并注册所有Tool"""
    import importlib
    import pkgutil
    from pathlib import Path

    tools_dir = Path(__file__).parent
    for _, name, _ in pkgutil.iter_modules([str(tools_dir)]):
        if name.endswith('_tool'):
            importlib.import_module(f"app.tools.{name}")
```

---

### Phase 3: 功能Agent层实现

#### 3.1 创建Agent基类
- **Description**: 提供Agent的通用实现，减少重复代码
- **Files to create**:
  - `backend/app/agents/base_agent.py`
- **Dependencies**: 1.2, 1.4
- **Code**:
```python
from app.agents.core import AgentProtocol, AgentRegistry, ToolRegistry

class BaseAgent:
    """Agent基类，提供通用功能"""

    name: str = "base_agent"
    description: str = ""
    tools: List[str] = []

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._tools: Dict[str, ToolProtocol] = {}
        self._init_tools()

    def _init_tools(self):
        """初始化依赖的Tools"""
        for tool_name in self.tools:
            tool = ToolRegistry.create(tool_name, self.config.get(tool_name))
            if tool:
                self._tools[tool_name] = tool

    async def use_tool(self, tool_name: str, input_data: Any, context: Optional[Dict] = None) -> Dict:
        """调用Tool"""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        return await tool.execute(input_data, context)
```

#### 3.2 实现WritingAgent
- **Description**: 撰写Agent，负责工艺内容编辑
- **Files to create**:
  - `backend/app/agents/functional/writing_agent.py`
- **Dependencies**: 3.1, 2.1, 2.4
- **Code**:
```python
@AgentRegistry.register("writing")
class WritingAgent(BaseAgent):
    """撰写Agent - 工艺内容编辑"""

    name = "writing"
    description = "负责工艺内容的编辑、表格填充、格式调整"
    tools = ["rag_retriever", "document_generator"]

    async def process(self, task: Dict, context: Optional[Dict] = None) -> Dict:
        """
        处理撰写任务

        task格式:
        {
            "action": "edit" | "fill" | "format",
            "target": "表格/段落标识",
            "content": "编辑内容",
            "requirements": "要求描述"
        }
        """
        action = task.get("action", "edit")

        # 1. 检索相关知识
        if task.get("requirements"):
            knowledge = await self.use_tool("rag_retriever", task["requirements"])

        # 2. 执行编辑
        if action == "edit":
            result = await self._do_edit(task, knowledge)
        elif action == "fill":
            result = await self._do_fill(task, knowledge)
        elif action == "format":
            result = await self._do_format(task)

        # 3. 生成文档
        doc = await self.use_tool("document_generator", result)

        return {"success": True, "result": result, "document": doc}
```

#### 3.3 实现ProofreadAgent
- **Description**: 校对Agent，负责术语标准化和数据纠正
- **Files to create**:
  - `backend/app/agents/functional/proofread_agent.py`
- **Dependencies**: 3.1, 2.1, 2.2
- **Code**:
```python
@AgentRegistry.register("proofread")
class ProofreadAgent(BaseAgent):
    """校对Agent - 术语标准化和数据纠正"""

    name = "proofread"
    description = "负责术语标准化、数据纠正补全、格式校验"
    tools = ["rag_retriever", "terminology_mapper"]

    async def process(self, task: Dict, context: Optional[Dict] = None) -> Dict:
        """
        处理校对任务

        task格式:
        {
            "content": "待校对内容",
            "check_type": "terminology" | "data" | "format" | "all"
        }
        """
        content = task.get("content", "")
        check_type = task.get("check_type", "all")

        results = {}

        # 术语标准化
        if check_type in ["terminology", "all"]:
            results["terminology"] = await self.use_tool("terminology_mapper", content)

        # 数据校验（基于知识库）
        if check_type in ["data", "all"]:
            results["data"] = await self._validate_data(content)

        return {"success": True, "results": results}
```

#### 3.4 实现ReviewAgent
- **Description**: 审查Agent，负责合规性和合理性检查
- **Files to create**:
  - `backend/app/agents/functional/review_agent.py`
- **Dependencies**: 3.1, 2.1, 2.3
- **Code**:
```python
@AgentRegistry.register("review")
class ReviewAgent(BaseAgent):
    """审查Agent - 合规性和合理性检查"""

    name = "review"
    description = "负责合规性检查、合理性验证、风险提示"
    tools = ["rag_retriever", "compliance_checker"]

    async def process(self, task: Dict, context: Optional[Dict] = None) -> Dict:
        """
        处理审查任务

        task格式:
        {
            "content": "待审查内容",
            "check_type": "compliance" | "rationality" | "all",
            "standards": ["enterprise", "industry", "safety"]
        }
        """
        content = task.get("content", "")
        check_type = task.get("check_type", "all")
        standards = task.get("standards", ["enterprise"])

        results = {}

        # 合规检查
        if check_type in ["compliance", "all"]:
            results["compliance"] = await self.use_tool(
                "compliance_checker",
                {"content": content, "standards": standards}
            )

        # 合理性验证
        if check_type in ["rationality", "all"]:
            results["rationality"] = await self._check_rationality(content)

        return {
            "success": True,
            "results": results,
            "passed": all(r.get("passed", False) for r in results.values())
        }
```

#### 3.5 创建functional模块初始化
- **Description**: 整合functional模块导出和自动发现
- **Files to create**:
  - `backend/app/agents/functional/__init__.py`
- **Dependencies**: 3.2-3.4

---

### Phase 4: Orchestrator重构

#### 4.1 重构ProcessOrchestrator
- **Description**: 更新Orchestrator使用新的Agent系统
- **Files to modify**:
  - `backend/app/agents/orchestrator/orchestrator.py`
- **Dependencies**: Phase 3完成
- **Code**:
```python
from app.agents.core import AgentRegistry
from app.agents.functional import discover_agents

class ProcessOrchestrator:
    """主控Agent - 协调功能Agent协作"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 初始化功能Agent
        self._agents: Dict[str, AgentProtocol] = {}
        self._init_agents()

        # 工作流定义
        self.workflows = {
            "edit": ["writing", "proofread", "review"],
            "quick_edit": ["writing", "proofread"],
            "review_only": ["review"],
            "proofread_only": ["proofread"]
        }

    def _init_agents(self):
        """初始化所有功能Agent"""
        for name in ["writing", "proofread", "review"]:
            agent = AgentRegistry.create(name, self.config.get(name))
            if agent:
                self._agents[name] = agent

    async def process_intent(self, user_input: str, context: Optional[Dict] = None) -> Dict:
        # 1. 识别意图
        intent = await self.intent_recognizer.recognize(user_input, context)

        # 2. 确定工作流
        workflow = self._select_workflow(intent)

        # 3. 执行工作流
        results = []
        for agent_name in workflow:
            agent = self._agents.get(agent_name)
            task = self._prepare_task_for_agent(intent, agent_name, results)
            result = await agent.process(task, context)
            results.append(result)

            # 如果校对/审查不通过，可能需要回退
            if not result.get("success") and agent_name in ["proofread", "review"]:
                # 处理失败情况
                pass

        return self._aggregate_results(results)
```

#### 4.2 更新意图识别
- **Description**: 添加对新工作流的意图识别
- **Files to modify**:
  - `backend/app/agents/orchestrator/intent_recognizer.py`
- **Dependencies**: 4.1

#### 4.3 更新任务分解
- **Description**: 将意图转换为Agent任务序列
- **Files to modify**:
  - `backend/app/agents/orchestrator/task_decomposer.py`
- **Dependencies**: 4.1

---

### Phase 5: PDF解析后台服务

#### 5.1 创建解析队列管理器
- **Description**: 管理PDF解析任务队列，限制并发数避免占满性能
- **Files to create**:
  - `backend/app/services/pdf_queue_manager.py`
- **Dependencies**: 无
- **Code**:
```python
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from collections import deque
from pathlib import Path

class ParseStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ParseTask:
    """解析任务"""
    pdf_path: Path
    output_dir: Path
    status: ParseStatus = ParseStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result_path: Optional[Path] = None

class PDFQueueManager:
    """
    PDF解析队列管理器

    功能：
    1. 任务队列管理（FIFO）
    2. 并发限制（默认2个并发）
    3. 状态跟踪和查询
    4. 失败重试机制
    5. 增量解析（避免重复解析已有文件）
    """

    def __init__(self, max_concurrent: int = 2, retry_count: int = 2, state_file: str = None):
        self.max_concurrent = max_concurrent  # 最大并发数
        self.retry_count = retry_count        # 失败重试次数
        self.state_file = Path(state_file) if state_file else None

        self._queue: deque[ParseTask] = deque()  # 等待队列
        self._processing: Dict[str, ParseTask] = {}  # 正在处理的任务
        self._completed: Dict[str, ParseTask] = {}   # 已完成任务（保留最近100个）
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # 已解析文件记录 {pdf_path: {hash, output_path, parsed_at}}
        self._parsed_files: Dict[str, Dict] = self._load_state()

        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def _load_state(self) -> Dict[str, Dict]:
        """加载已解析文件状态"""
        if self.state_file and self.state_file.exists():
            try:
                import json
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("failed_to_load_parse_state", error=str(e))
        return {}

    def _save_state(self):
        """保存已解析文件状态"""
        if self.state_file:
            try:
                import json
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(self._parsed_files, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error("failed_to_save_parse_state", error=str(e))

    def _get_file_hash(self, pdf_path: Path) -> str:
        """计算文件hash（用于检测文件是否变化）"""
        import hashlib
        hasher = hashlib.md5()
        # 只读取前1MB和最后1MB，避免大文件耗时过长
        file_size = pdf_path.stat().st_size
        with open(pdf_path, 'rb') as f:
            # 前1MB
            hasher.update(f.read(min(1024*1024, file_size)))
            # 最后1MB
            if file_size > 1024*1024:
                f.seek(-min(1024*1024, file_size), 2)
                hasher.update(f.read())
        return hasher.hexdigest()

    def is_already_parsed(self, pdf_path: Path) -> bool:
        """
        检查文件是否已解析且未变化

        Returns:
            True: 已解析，无需重新解析
            False: 未解析或文件已变化，需要解析
        """
        path_key = str(pdf_path.resolve())

        if path_key not in self._parsed_files:
            return False

        # 检查输出文件是否存在
        record = self._parsed_files[path_key]
        output_path = Path(record.get('output_path', ''))
        if not output_path.exists():
            return False

        # 检查文件hash是否变化
        try:
            current_hash = self._get_file_hash(pdf_path)
            if current_hash != record.get('hash'):
                logger.info("pdf_file_changed", path=str(pdf_path))
                return False
        except Exception as e:
            logger.warning("failed_to_check_hash", path=str(pdf_path), error=str(e))
            return False

        return True

    async def add_task(self, pdf_path: Path, output_dir: Path, force: bool = False) -> str:
        """
        添加解析任务到队列

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            force: 是否强制重新解析（忽略已解析记录）

        Returns:
            任务ID，如果已解析则返回空字符串
        """
        # 检查是否已解析
        if not force and self.is_already_parsed(pdf_path):
            logger.info("pdf_already_parsed_skipped", path=str(pdf_path))
            return ""

        task = ParseTask(pdf_path=pdf_path, output_dir=output_dir)
        task_id = self._generate_task_id(pdf_path)

        self._queue.append(task)
        logger.info("pdf_task_added", task_id=task_id, pdf=str(pdf_path), queue_size=len(self._queue))

        return task_id

    async def start(self):
        """启动队列处理器"""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        """停止队列处理器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()

    async def add_task(self, pdf_path: Path, output_dir: Path) -> str:
        """
        添加解析任务到队列

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（保持与源文件相同的相对路径结构）

        Returns:
            任务ID
        """
        task = ParseTask(pdf_path=pdf_path, output_dir=output_dir)
        task_id = self._generate_task_id(pdf_path)

        self._queue.append(task)
        logger.info("pdf_task_added", task_id=task_id, pdf=str(pdf_path), queue_size=len(self._queue))

        return task_id

    def _generate_task_id(self, pdf_path: Path) -> str:
        """生成任务ID（基于文件路径，不含时间戳）"""
        return str(pdf_path).replace("\\", "/").replace("/", "_").replace(":", "")

    async def _process_queue(self):
        """队列处理循环"""
        while self._running:
            if not self._queue:
                await asyncio.sleep(1)
                continue

            # 等待获取信号量（控制并发）
            async with self._semaphore:
                if self._queue:
                    task = self._queue.popleft()
                    task_id = self._generate_task_id(task.pdf_path)
                    self._processing[task_id] = task

                    # 异步执行解析
                    asyncio.create_task(self._execute_parse(task_id, task))

            await asyncio.sleep(0.1)

    async def _execute_parse(self, task_id: str, task: ParseTask):
        """执行单个解析任务"""
        task.status = ParseStatus.PROCESSING
        task.started_at = datetime.now()

        try:
            # 调用实际的PDF解析器
            result = await self._parse_pdf(task.pdf_path, task.output_dir)
            task.status = ParseStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result_path = result

            # 记录已解析文件
            path_key = str(task.pdf_path.resolve())
            self._parsed_files[path_key] = {
                'hash': self._get_file_hash(task.pdf_path),
                'output_path': str(result),
                'parsed_at': task.completed_at.isoformat()
            }
            self._save_state()

            logger.info("pdf_parse_completed", task_id=task_id, duration_seconds=(task.completed_at - task.started_at).total_seconds())

        except Exception as e:
            task.status = ParseStatus.FAILED
            task.error = str(e)
            logger.error("pdf_parse_failed", task_id=task_id, error=str(e))

        finally:
            # 移动到完成列表
            del self._processing[task_id]
            self._completed[task_id] = task

            # 限制完成列表大小
            if len(self._completed) > 100:
                oldest_key = next(iter(self._completed))
                del self._completed[oldest_key]

    async def _parse_pdf(self, pdf_path: Path, output_base_dir: Path) -> Path:
        """
        解析PDF文件

        输出规则：
        1. 保持与源文件相同的相对路径结构
        2. HTML文件名 = PDF文件名（不含.pdf后缀，不加时间戳）
        """
        # 计算相对路径（保持文件夹结构）
        # 例如：input/工艺文件/电缆/G5a.pdf -> output/工艺文件/电缆/G5a/G5a.html
        relative_path = pdf_path.relative_to(self.watch_dir) if hasattr(self, 'watch_dir') else pdf_path.name
        pdf_name = pdf_path.stem  # 文件名（不含后缀）

        # 输出目录：保持原有文件夹结构
        output_dir = output_base_dir / relative_path.parent / pdf_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # 输出文件：使用PDF文件名（不加时间戳）
        output_html = output_dir / f"{pdf_name}.html"

        # 调用PDF解析器
        # ... 实际解析逻辑

        return output_html

    def get_status(self, task_id: str = None) -> Dict:
        """获取任务状态"""
        if task_id:
            if task_id in self._processing:
                return {"status": "processing", "task": self._processing[task_id]}
            if task_id in self._completed:
                return {"status": "completed", "task": self._completed[task_id]}
            return {"status": "not_found"}

        return {
            "queue_size": len(self._queue),
            "processing_count": len(self._processing),
            "completed_count": len(self._completed),
            "max_concurrent": self.max_concurrent
        }
```

#### 5.2 创建PDF文件监听服务
- **Description**: 监听文件夹变化，将新PDF加入队列
- **Files to create**:
  - `backend/app/services/pdf_watcher_service.py`
- **Dependencies**: 5.1
- **Code**:
```python
import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.services.pdf_queue_manager import PDFQueueManager
from app.shared.logging import get_logger

logger = get_logger(__name__)


class PDFWatcherService:
    """
    PDF文件监听服务

    功能：
    1. 监听指定文件夹（支持子目录）
    2. 检测到新PDF文件时加入解析队列
    3. 与队列管理器配合，控制并发解析
    4. 增量解析：只解析新文件/变化文件，不重复解析已有文件
    """

    def __init__(
        self,
        watch_dir: str,
        output_dir: str,
        max_concurrent: int = 2,  # 最大并发解析数，避免占满性能
        state_file: str = None    # 状态文件路径，用于记录已解析文件
    ):
        self.watch_dir = Path(watch_dir)
        self.output_dir = Path(output_dir)
        self.observer = Observer()

        # 状态文件路径（默认存放在output目录下）
        if state_file is None:
            state_file = str(self.output_dir / ".parse_state.json")

        # 队列管理器（带状态持久化）
        self.queue_manager = PDFQueueManager(
            max_concurrent=max_concurrent,
            state_file=state_file
        )

        logger.info(
            "pdf_watcher_initialized",
            watch_dir=str(self.watch_dir),
            output_dir=str(self.output_dir),
            max_concurrent=max_concurrent,
            state_file=state_file
        )

    async def start(self):
        """启动监听和队列处理"""
        # 启动队列处理器
        await self.queue_manager.start()

        # 扫描已有文件（只添加未解析的）
        await self._scan_existing_files()

        # 启动文件监听
        event_handler = PDFEventHandler(self.queue_manager, self.watch_dir, self.output_dir)
        self.observer.schedule(event_handler, str(self.watch_dir), recursive=True)  # recursive=True 支持子目录
        self.observer.start()

        logger.info("pdf_watcher_started")

    async def _scan_existing_files(self):
        """
        扫描已有PDF文件，只添加未解析的到队列

        这个方法确保：
        1. 服务重启时不会重复解析已有文件
        2. 用户往文件夹添加多个PDF时，只解析新的
        """
        existing_pdfs = list(self.watch_dir.rglob("*.pdf"))
        new_count = 0

        for pdf_path in existing_pdfs:
            # 检查是否已解析（通过hash比对）
            if not self.queue_manager.is_already_parsed(pdf_path):
                await self.queue_manager.add_task(pdf_path, self.output_dir)
                new_count += 1

        logger.info(
            "existing_files_scanned",
            total_pdfs=len(existing_pdfs),
            new_pdfs=new_count,
            already_parsed=len(existing_pdfs) - new_count
        )

    async def stop(self):
        """停止监听"""
        await self.queue_manager.stop()
        self.observer.stop()
        self.observer.join()
        logger.info("pdf_watcher_stopped")

    def get_status(self):
        """获取服务状态"""
        return self.queue_manager.get_status()


class PDFEventHandler(FileSystemEventHandler):
    """PDF文件事件处理器"""

    def __init__(self, queue_manager: PDFQueueManager, watch_dir: Path, output_dir: Path):
        self.queue_manager = queue_manager
        self.watch_dir = watch_dir
        self.output_dir = output_dir

    def on_created(self, event):
        """文件创建事件"""
        if event.is_directory:
            return

        if event.src_path.lower().endswith('.pdf'):
            # 加入解析队列（异步）
            asyncio.create_task(self._add_to_queue(event.src_path))

    def on_moved(self, event):
        """文件移动事件（也处理重命名）"""
        if event.is_directory:
            return

        if event.dest_path.lower().endswith('.pdf'):
            asyncio.create_task(self._add_to_queue(event.dest_path))

    async def _add_to_queue(self, pdf_path: str):
        """
        将PDF加入解析队列

        注意：add_task内部会检查是否已解析，不会重复添加
        """
        pdf_path = Path(pdf_path)

        # 等待文件写入完成（简单延迟）
        await asyncio.sleep(2)

        # 检查文件是否可读
        if not pdf_path.exists():
            logger.warning("pdf_file_not_found", path=str(pdf_path))
            return

        # 加入队列（内部会检查是否已解析）
        task_id = await self.queue_manager.add_task(pdf_path, self.output_dir)

        if task_id:
            logger.info("pdf_added_to_queue", task_id=task_id, path=str(pdf_path))
        else:
            logger.debug("pdf_already_parsed_skipped", path=str(pdf_path))
```

#### 5.3 创建解析状态API
- **Description**: 提供解析状态的查询接口
- **Files to create**:
  - `backend/app/api/pdf_status.py`
- **Dependencies**: 5.1, 5.2
- **Code**:
```python
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/pdf", tags=["PDF解析"])

# 全局服务实例（在main.py中注入）
_pdf_watcher_service = None

def set_pdf_watcher_service(service):
    global _pdf_watcher_service
    _pdf_watcher_service = service

@router.get("/status")
async def get_parse_status(task_id: Optional[str] = Query(None, description="任务ID")):
    """获取PDF解析状态"""
    if _pdf_watcher_service:
        return _pdf_watcher_service.get_status()
    return {"error": "Service not initialized"}

@router.get("/queue")
async def get_queue_status():
    """获取队列状态"""
    if _pdf_watcher_service:
        return _pdf_watcher_service.queue_manager.get_status()
    return {"error": "Service not initialized"}
```

#### 5.4 集成到启动流程
- **Description**: 应用启动时自动启动PDF监听
- **Files to modify**:
  - `backend/main.py`
- **Dependencies**: 5.1-5.3
- **Code**:
```python
# main.py 中添加

from app.services.pdf_watcher_service import PDFWatcherService
from app.api.pdf_status import set_pdf_watcher_service

# 全局服务实例
pdf_watcher: Optional[PDFWatcherService] = None

@app.on_event("startup")
async def startup_event():
    global pdf_watcher

    # ... 其他初始化 ...

    # 启动PDF监听服务
    pdf_watch_dir = settings.DATA_DIR / "pdf_input"
    pdf_output_dir = settings.DATA_DIR / "pdf_output"
    pdf_watch_dir.mkdir(parents=True, exist_ok=True)
    pdf_output_dir.mkdir(parents=True, exist_ok=True)

    pdf_watcher = PDFWatcherService(
        watch_dir=str(pdf_watch_dir),
        output_dir=str(pdf_output_dir),
        max_concurrent=2  # 最多同时解析2个PDF
    )
    await pdf_watcher.start()
    set_pdf_watcher_service(pdf_watcher)

    logger.info("pdf_watcher_service_started",
                watch_dir=str(pdf_watch_dir),
                output_dir=str(pdf_output_dir))

@app.on_event("shutdown")
async def shutdown_event():
    global pdf_watcher
    if pdf_watcher:
        await pdf_watcher.stop()
```

#### 5.5 输出路径规则说明
- **Description**: 定义PDF解析输出的路径和命名规则
- **Rules**:

```
输入文件结构:
  pdf_input/
  ├── 电缆工艺/
  │   ├── G5a.pdf
  │   └── G10a.pdf
  └── 机械加工/
      └── 工艺卡.pdf

输出文件结构（保持相同文件夹结构，文件名=PDF名）:
  pdf_output/
  ├── 电缆工艺/
  │   ├── G5a/
  │   │   ├── G5a.html      # 主HTML文件
  │   │   ├── G5a.json      # 解析元数据
  │   │   └── images/       # 提取的图片
  │   └── G10a/
  │       └── G10a.html
  └── 机械加工/
      └── 工艺卡/
          └── 工艺卡.html

规则：
1. 输出目录 = output_base / 相对路径 / PDF文件名
2. HTML文件名 = PDF文件名.html（不加时间戳）
3. 同一PDF重复放入时，覆盖旧文件（不生成副本）
```

---

### Phase 6: 清理旧代码

#### 6.1 删除旧的SubAgent
- **Description**: 删除不再使用的sub_agents目录
- **Files to delete**:
  - `backend/app/agents/sub_agents/` (整个目录)
- **Dependencies**: Phase 3, 4完成

#### 6.2 保留并整理Tools
- **Description**: 保留有用的tools，删除冗余
- **Files to keep**:
  - `backend/app/tools/pdf_parser.py` (被后台服务使用)
  - `backend/app/tools/vector_store.py` (被RAGRetriever使用)
- **Files to refactor**:
  - 其他tools按新接口重构

#### 6.3 更新导入
- **Description**: 更新所有导入路径
- **Files to modify**:
  - 所有引用旧Agent/Tool的文件
- **Dependencies**: 6.1, 6.2

---

### Phase 7: 测试和文档

#### 7.1 单元测试
- **Description**: 为新组件编写单元测试
- **Files to create**:
  - `backend/tests/agents/core/test_registry.py`
  - `backend/tests/agents/functional/test_writing_agent.py`
  - `backend/tests/agents/functional/test_proofread_agent.py`
  - `backend/tests/agents/functional/test_review_agent.py`
- **Dependencies**: Phase 1-6

#### 7.2 集成测试
- **Description**: 测试完整工作流
- **Files to create**:
  - `backend/tests/integration/test_orchestrator_workflow.py`
- **Dependencies**: 7.1

#### 7.3 更新文档
- **Description**: 更新架构文档
- **Files to modify**:
  - `CLAUDE.md`
  - `docs/architecture.md` (如存在)
- **Dependencies**: 7.2

---

## Codebase Integration Points

### Files to Modify
- `backend/app/agents/orchestrator/orchestrator.py` - 主控重构
- `backend/app/agents/orchestrator/intent_recognizer.py` - 意图识别
- `backend/app/agents/orchestrator/task_decomposer.py` - 任务分解
- `backend/main.py` - 启动PDF监听服务
- `backend/app/tools/__init__.py` - Tool自动发现

### New Files to Create
- `backend/app/agents/core/__init__.py` - 核心模块
- `backend/app/agents/core/protocols.py` - Protocol定义
- `backend/app/agents/core/registry.py` - 注册表
- `backend/app/agents/base_agent.py` - Agent基类
- `backend/app/agents/functional/__init__.py` - 功能Agent模块
- `backend/app/agents/functional/writing_agent.py`
- `backend/app/agents/functional/proofread_agent.py`
- `backend/app/agents/functional/review_agent.py`
- `backend/app/tools/rag_retriever.py` - RAG检索Tool
- `backend/app/tools/terminology_tool.py` - 术语Tool
- `backend/app/tools/compliance_tool.py` - 合规Tool
- `backend/app/tools/document_tool.py` - 文档Tool
- `backend/app/services/pdf_watcher_service.py` - PDF监听服务
- `backend/app/api/pdf_status.py` - 解析状态API

### Files to Delete
- `backend/app/agents/sub_agents/` - 整个目录

### Existing Patterns to Follow
- 使用 `app.shared.logging.get_logger` 进行日志
- 配置通过 `config` 字典传入
- 异步方法返回 `Dict[str, Any]`
- 错误返回格式: `{"success": False, "error": "...", "error_code": "..."}`

---

## Technical Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户输入                                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ProcessOrchestrator                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │
│  │ Intent      │  │ Task        │  │ Workflow    │                      │
│  │ Recognizer  │  │ Decomposer  │  │ Manager     │                      │
│  └─────────────┘  └─────────────┘  └─────────────┘                      │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  WritingAgent   │     │ ProofreadAgent  │     │  ReviewAgent    │
│  (撰写)         │     │  (校对)         │     │  (审查)         │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           ToolRegistry                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ RAGRetriever│  │ Terminology │  │ Compliance  │  │ Document    │    │
│  │             │  │ Mapper      │  │ Checker     │  │ Generator   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        后台服务（独立进程）                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    PDFWatcherService                             │    │
│  │  监听文件夹 → 加入队列 → 并发控制(2) → 解析 → 保持目录结构输出     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    PDFQueueManager                               │    │
│  │  任务队列 | 并发限制(max=2) | 状态跟踪 | 失败重试                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. 用户输入工艺意图
       ↓
2. Orchestrator识别意图 → 选择工作流
       ↓
3. WritingAgent执行编辑
   - 调用RAGRetriever获取相关知识
   - 执行编辑操作
   - 调用DocumentGenerator生成草稿
       ↓
4. ProofreadAgent执行校对
   - 调用TerminologyMapper标准化术语
   - 验证数据完整性
   - 返回修改建议
       ↓
5. ReviewAgent执行审查
   - 调用ComplianceChecker检查合规
   - 验证合理性
   - 返回审查结果
       ↓
6. Orchestrator聚合结果 → 返回用户
```

### API Endpoints

- `POST /api/tasks` - 创建新任务
- `POST /api/tasks/{id}/process` - 处理用户意图
- `GET /api/tasks/{id}/status` - 获取任务状态
- `GET /api/pdf/status` - 获取PDF解析状态
- `GET /api/agents` - 列出可用Agent
- `GET /api/tools` - 列出可用Tool

---

## Dependencies and Libraries

| 库 | 用途 | 状态 |
|---|---|---|
| typing.Protocol | 接口定义 | 内置 |
| watchdog | 文件监听 | 需安装 |
| asyncio | 异步支持 | 内置 |
| asyncio.Semaphore | 并发控制 | 内置 |
| collections.deque | 任务队列 | 内置 |

---

## Testing Strategy

### Unit Tests
- `test_registry.py` - 注册表功能测试
- `test_protocols.py` - Protocol接口验证
- `test_writing_agent.py` - 撰写Agent测试
- `test_proofread_agent.py` - 校对Agent测试
- `test_review_agent.py` - 审查Agent测试

### Integration Tests
- `test_orchestrator_workflow.py` - 完整工作流测试
- `test_pdf_watcher.py` - PDF监听服务测试

### Edge Cases
- Tool不存在时的处理
- Agent执行失败时的回退
- PDF解析失败时的重试
- 并发任务处理

---

## Success Criteria

- [ ] 新增Tool只需添加装饰器，无需修改核心代码
- [ ] 新增Agent只需继承BaseAgent并注册
- [ ] 工作流可配置，支持自定义Agent序列
- [ ] PDF解析独立运行，不影响主流程
- [ ] PDF解析有队列管理，并发数可控（默认2个）
- [ ] PDF输出保持原有目录结构，文件名不加时间戳
- [ ] PDF增量解析：服务重启/添加新文件时不重复解析已有文件
- [ ] 所有测试通过
- [ ] 代码符合现有规范（日志、错误处理）

---

## Notes and Considerations

### PDF解析输出规则
- **目录结构**：保持与源PDF相同的相对路径结构
- **文件命名**：HTML文件名 = PDF文件名（不加时间戳）
- **重复处理**：同一PDF重复放入时覆盖旧文件
- **并发控制**：默认最大2个并发解析任务

### 增量解析机制（避免重复解析）
- **状态持久化**：已解析文件记录保存到 `pdf_parse_state.json`
- **Hash比对**：通过文件hash检测内容是否变化
- **启动扫描**：服务启动时只添加未解析的PDF
- **场景覆盖**：
  1. 服务重启 → 不重复解析已有文件
  2. 用户添加新PDF → 只解析新的
  3. 用户覆盖已有PDF → 检测到变化后重新解析

### 向后兼容
- 保留现有API接口
- Repository和ContextManager继续工作
- 渐进式迁移，可分阶段上线

### 性能考虑
- Agent实例可复用，避免重复初始化
- Tool实例缓存在Agent内部
- PDF解析异步进行，不阻塞主流程

### 扩展性
- 新增功能Agent只需3步：
  1. 继承BaseAgent
  2. 添加@AgentRegistry.register装饰器
  3. 在Orchestrator工作流中引用

- 新增Tool只需2步：
  1. 实现ToolProtocol
  2. 添加@ToolRegistry.register装饰器

### 潜在风险
- PDF监听服务需要独立进程管理
- Agent间通信需要标准化
- 错误传播需要妥善处理

---

*This plan is ready for execution with `/execute-plan`*
