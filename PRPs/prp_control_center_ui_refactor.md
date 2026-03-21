# PRP: Control Center UI 重构

## 项目元数据

```yaml
项目名称: Control Center UI 重构 - Evolver 状态展示 + 本地任务读取
项目ID: PRP-CC-001
创建日期: 2026-03-19
优先级: P0 (架构级改进)
预估工时: 3-4 天
状态: COMPLETED
完成日期: 2026-03-19
```

## 背景与问题陈述

### 当前问题

1. **任务状态显示不正确**
   - Control Center 从 OpenClaw Gateway 获取任务数据
   - 我们的 Coder Agent 使用 Claude CLI，不经过 Gateway
   - UI 显示的任务状态与实际不符

2. **无法展示 Evolver 状态**
   - Evolver 是项目监督和自进化系统
   - 用户无法看到 Evolver 的学习进度
   - 无法查看已固化的 skills、开发策略、使用习惯等

3. **Coder 工作状态不可见**
   - Coder 启动 Claude Code CLI 后，用户看不到终端
   - 无法知道 Coder 是否在运行
   - 无法查看执行进度

---

## 目标架构

```yaml
数据流:
  Evolver → runtime/tasks.json → Control Center UI
  Evolver → queue/knowledge/gep/ → Control Center UI
  
读取方式:
  - 任务数据: 直接从 runtime/tasks.json 读取
  - Evolver 状态: 从 genes.json + events.jsonl 读取
  - Coder 状态: 检测 claude.exe 进程 + 读取日志
  
不依赖:
  - OpenClaw Gateway（可选，作为备用数据源）
```

---

## piv 拆分

### piv_001: Evolver 状态 API

**文件**: `src/runtime/evolver-status.ts` (新建)

**功能**: 读取 Evolver 自进化状态

**代码量**: 80 行

**实现**:
```typescript
interface EvolverStatus {
  status: 'active' | 'paused';
  learnedCount: {
    issues: number;
    skills: number;
    genes: number;
  };
  recentSkills: Skill[];
  recentEvents: Event[];
}

function getEvolverStatus(): EvolverStatus {
  // 读取 genes.json
  // 读取 events.jsonl
  // 读取 skills/ 目录
  // 统计数量
}
```

**验收标准**:
- 返回正确的 Evolver 状态
- 包含已学习内容数量
- 包含最近的 skills 和 events

---

### piv_002: Evolver 状态 API 端点

**文件**: `src/ui/server.ts`

**功能**: 添加 `/api/evolver/status` 端点

**代码量**: 30 行

**实现**:
```typescript
if (method === "GET" && path === "/api/evolver/status") {
  const status = getEvolverStatus();
  return writeJson(res, 200, { ok: true, status });
}
```

**验收标准**:
- GET `/api/evolver/status` 返回正确数据
- 响应时间 < 100ms

---

### piv_003: Evolver 状态 UI 组件

**文件**: `src/ui/components/evolver-status.tsx` (新建)

**功能**: 展示 Evolver 状态的 UI 组件

**代码量**: 100 行

**实现**:
```tsx
function EvolverStatusCard({ status }: { status: EvolverStatus }) {
  return (
    <div className="evolver-status-card">
      <h3>Evolver 自进化系统</h3>
      <div>状态: {status.status === 'active' ? '🟢 活跃' : '🟡 暂停'}</div>
      <div>已学习: {status.learnedCount.skills} skills</div>
      <div>最近固化: {status.recentSkills[0]?.name}</div>
    </div>
  );
}
```

**验收标准**:
- 显示 Evolver 状态
- 显示已学习内容数量
- 显示最近的 skills

---

### piv_004: 任务栏本地读取逻辑

**文件**: `src/runtime/task-local-reader.ts` (新建)

**功能**: 直接从 runtime/tasks.json 读取任务

**代码量**: 50 行

**实现**:
```typescript
function readLocalTasks(): TaskStoreSnapshot {
  const content = fs.readFileSync(TASKS_PATH, 'utf-8');
  const data = JSON.parse(content);
  
  // 映射状态
  data.tasks = data.tasks.map(task => ({
    ...task,
    status: mapTaskStatus(task.status),
  }));
  
  return data;
}

function mapTaskStatus(status: string): TaskState {
  switch (status) {
    case "completed": return "done";
    case "pending": return "todo";
    case "in_progress": return "in_progress";
    case "failed":
    case "blocked": return "blocked";
    default: return "todo";
  }
}
```

**验收标准**:
- 正确读取 tasks.json
- 正确映射状态
- 性能 < 50ms

---

### piv_005: 修改任务 API 端点

**文件**: `src/ui/server.ts`

**功能**: 修改 `/api/tasks` 端点，优先读取本地文件

**代码量**: 40 行

**实现**:
```typescript
if (method === "GET" && (path === "/tasks" || path === "/api/tasks")) {
  // 优先从本地读取
  const localTasks = readLocalTasks();
  
  // 如果本地有数据，直接返回
  if (localTasks.tasks.length > 0) {
    const filters = parseTaskFilters(url.searchParams, path === "/api/tasks");
    const allTasks = listTasks(localTasks, projectTitleMap(snapshot));
    const filteredTasks = applyTaskFilters(allTasks, filters);
    return writeJson(res, 200, {
      ok: true,
      tasks: filteredTasks,
      updatedAt: localTasks.updatedAt,
    });
  }
  
  // 否则从 Gateway 读取（向后兼容）
  const snapshot = await readReadModelSnapshot();
  // ... 原有逻辑
}
```

**验收标准**:
- 优先从本地读取
- 本地无数据时回退到 Gateway
- 返回正确的任务状态

---

### piv_006: Coder 工作状态 API

**文件**: `src/runtime/coder-status.ts` (新建)

**功能**: 检测 Coder 进程状态

**代码量**: 60 行

**实现**:
```typescript
interface CoderStatus {
  status: 'running' | 'idle' | 'error';
  currentTask?: string;
  process?: {
    pid: number;
    command: string;
    startedAt: string;
  };
  logs: string[];
}

function getCoderStatus(): CoderStatus {
  // 检测 claude.exe 进程
  const claudeProcess = detectClaudeProcess();
  
  if (!claudeProcess) {
    return { status: 'idle', logs: [] };
  }
  
  // 读取当前任务
  const currentTask = getCurrentTaskFromTasksJson();
  
  // 读取日志
  const logs = readRecentLogs(currentTask, 5);
  
  return {
    status: 'running',
    currentTask,
    process: claudeProcess,
    logs,
  };
}

function detectClaudeProcess(): ProcessInfo | null {
  // 使用 tasklist 或 ps 命令检测
  const result = execSync('tasklist /FI "IMAGENAME eq claude.exe" /FO CSV');
  // 解析结果
}
```

**验收标准**:
- 正确检测 claude.exe 进程
- 返回进程 PID 和启动时间
- 读取最近 5 行日志

---

### piv_007: Coder 状态 API 端点

**文件**: `src/ui/server.ts`

**功能**: 添加 `/api/agents/coder/status` 端点

**代码量**: 20 行

**实现**:
```typescript
if (method === "GET" && path === "/api/agents/coder/status") {
  const status = getCoderStatus();
  return writeJson(res, 200, { ok: true, status });
}
```

**验收标准**:
- GET `/api/agents/coder/status` 返回正确数据
- 实时反映进程状态

---

### piv_008: Coder 状态 UI 组件

**文件**: `src/ui/components/coder-status.tsx` (新建)

**功能**: 展示 Coder 工作状态的 UI 组件

**代码量**: 80 行

**实现**:
```tsx
function CoderStatusCard({ status }: { status: CoderStatus }) {
  return (
    <div className="coder-status-card">
      <h3>Coder Agent</h3>
      <div>状态: {status.status === 'running' ? '🟢 运行中' : '⚪ 空闲'}</div>
      {status.currentTask && <div>任务: {status.currentTask}</div>}
      {status.process && (
        <>
          <div>工具: Claude Code CLI</div>
          <div>进程: claude.exe (PID {status.process.pid})</div>
        </>
      )}
      <div>日志: {status.logs.join('\n')}</div>
    </div>
  );
}
```

**验收标准**:
- 显示 Coder 状态
- 显示当前任务
- 显示进程信息
- 显示最近日志

---

### piv_009: 集成到 UI

**文件**: `src/ui/server.ts` 或 UI 模板

**功能**: 将 Evolver 和 Coder 状态集成到 UI

**代码量**: 30 行

**实现**:
- 在 "当前活跃智能体" 区域显示 Evolver 和 Coder 卡片
- 每 5 秒刷新一次状态
- 使用 WebSocket 或轮询

**验收标准**:
- UI 正确显示 Evolver 和 Coder 状态
- 状态实时更新

---

### piv_010: 测试

**文件**: `tests/control-center-ui.test.ts` (新建)

**功能**: 单元测试和集成测试

**代码量**: 150 行

**测试用例**:
1. 测试 `readLocalTasks()` 函数
2. 测试 `mapTaskStatus()` 函数
3. 测试 `/api/tasks` 端点
4. 测试 `/api/evolver/status` 端点
5. 测试 `/api/agents/coder/status` 端点
6. 测试 UI 渲染

**验收标准**:
- 所有测试通过
- 覆盖率 > 80%

---

## 数据流设计

```yaml
任务数据流:
  1. Coder 完成任务 → 写入 runtime/tasks.json
  2. Evolver 定期同步 → 调用 control-center-sync
  3. UI 读取 → GET /api/tasks → readLocalTasks()
  
Evolver 数据流:
  1. Evolver 运行 → 更新 genes.json + events.jsonl
  2. UI 读取 → GET /api/evolver/status → getEvolverStatus()
  
Coder 状态流:
  1. Coder 启动 → claude.exe 进程
  2. UI 检测 → GET /api/agents/coder/status → getCoderStatus()
  3. 实时更新 → 每 5 秒轮询
```

---

## 技术方案

### 方案 1: 直接读取本地文件（推荐）

**优点**:
- 简单直接
- 不依赖 Gateway
- 性能好

**缺点**:
- 需要确保文件同步

### 方案 2: 混合方案（向后兼容）

**优点**:
- 向后兼容
- Gateway 数据作为备用

**缺点**:
- 逻辑复杂
- 需要处理数据冲突

---

## 测试策略

### 单元测试

```yaml
测试文件: tests/control-center-ui.test.ts
覆盖率: > 80%

测试用例:
  - readLocalTasks() - 读取 tasks.json
  - mapTaskStatus() - 状态映射
  - getEvolverStatus() - Evolver 状态
  - getCoderStatus() - Coder 状态
```

### 集成测试

```yaml
测试方式:
  1. 更新 tasks.json
  2. 调用 /api/tasks
  3. 验证返回正确状态
```

### 手动测试

```yaml
测试步骤:
  1. 启动 Control Center
  2. 更新 tasks.json（标记任务为 completed）
  3. 刷新浏览器
  4. 验证 UI 显示"已完成"
  5. 检查 Evolver 状态卡片
  6. 检查 Coder 状态卡片
```

---

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 文件读取失败 | 中 | 添加错误处理，回退到 Gateway |
| 缓存不一致 | 低 | 修改文件时清除缓存 |
| 进程检测失败 | 低 | 多种检测方式（tasklist + ps） |
| UI 性能问题 | 低 | 使用缓存，5 秒刷新一次 |

---

## 回滚计划

**Feature Flag**:
```typescript
const USE_LOCAL_TASKS = process.env.USE_LOCAL_TASKS === 'true';
```

**回滚步骤**:
1. 设置 `USE_LOCAL_TASKS=false`
2. 重启 Control Center
3. 验证 Gateway 数据源工作正常

---

## 时间估算

| piv | 预估时间 |
|-----|---------|
| piv_001 - Evolver 状态 API | 2 小时 |
| piv_002 - API 端点 | 1 小时 |
| piv_003 - UI 组件 | 3 小时 |
| piv_004 - 任务本地读取 | 2 小时 |
| piv_005 - 任务 API 修改 | 2 小时 |
| piv_006 - Coder 状态 API | 2 小时 |
| piv_007 - API 端点 | 1 小时 |
| piv_008 - UI 组件 | 2 小时 |
| piv_009 - UI 集成 | 2 小时 |
| piv_010 - 测试 | 4 小时 |
| **总计** | **21 小时 (3-4 天)** |

---

_创建时间: 2026-03-19 14:10_
