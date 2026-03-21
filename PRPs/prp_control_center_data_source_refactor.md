# PRP: Control Center 数据源彻底重构

## 项目元数据

```yaml
项目名称: Control Center 数据源彻底重构 - 完全本地化
项目ID: PRP-CC-002
创建日期: 2026-03-19
优先级: P0 (数据准确性问题)
预估工时: 4-6 小时
状态: PLANNING
```

## 背景与问题陈述

### 当前问题

**根本原因**：
- Control Center 从 OpenClaw Gateway 获取 snapshot
- Gateway 返回的 snapshot 包含**旧任务数据**（3 完成, 1 进行中, 4 待办）
- 本地 `tasks.json` 有**新任务数据**（1 完成）
- 合并逻辑保留了 Gateway 的旧数据
- **结果**：UI 显示错误的项目进度（38% 而不是 100%）

**数据流**：
```
OpenClaw Gateway (旧数据)
    ↓
monitor.ts: saveSnapshot(snapshot)
    ↓
snapshot-store.ts: mergeLocalTasks() ← 只合并，不覆盖
    ↓
last-snapshot.json (旧 + 新 = 错误)
    ↓
UI 显示错误数据
```

---

## 目标架构

### 方案：完全本地化（推荐）

**核心原则**：
- ❌ **不从 Gateway 获取任务数据**
- ✅ **任务数据 100% 来自本地 tasks.json**
- ✅ **Gateway 数据只用于会话、Cron 等非任务信息**

**新数据流**：
```
本地 tasks.json (唯一数据源)
    ↓
task-local-reader.ts (新模块)
    ↓
snapshot-store.ts (合并到 snapshot.tasks)
    ↓
last-snapshot.json (正确的任务数据)
    ↓
UI 显示正确数据
```

---

## piv 拆分

### piv_001: 创建 task-local-reader.ts

**文件**: `src/runtime/task-local-reader.ts` (新建)

**功能**: 读取本地 tasks.json 并映射状态

**代码量**: 80 行

**实现**:
```typescript
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { existsSync } from "node:fs";
import type { TaskState, TaskStoreSnapshot, ProjectTask } from "../types";

const RUNTIME_DIR = join(process.cwd(), "runtime");
const TASKS_PATH = join(RUNTIME_DIR, "tasks.json");

/**
 * 读取本地 tasks.json
 */
export async function readLocalTasks(): Promise<TaskStoreSnapshot | null> {
  if (!existsSync(TASKS_PATH)) {
    return null;
  }

  try {
    const content = await readFile(TASKS_PATH, "utf8");
    const data = JSON.parse(content);

    // 映射状态
    if (data.tasks && Array.isArray(data.tasks)) {
      data.tasks = data.tasks.map((task: any) => ({
        ...task,
        status: mapTaskStatus(task.status),
      }));
    }

    return data as TaskStoreSnapshot;
  } catch (error) {
    console.error("读取 tasks.json 失败:", error);
    return null;
  }
}

/**
 * 映射任务状态
 */
function mapTaskStatus(status: string): TaskState {
  switch (status) {
    case "completed":
      return "done";
    case "pending":
      return "todo";
    case "in_progress":
      return "in_progress";
    case "failed":
    case "blocked":
      return "blocked";
    default:
      return "todo";
  }
}

/**
 * 计算项目进度
 */
export function calculateProjectProgress(tasks: ProjectTask[]): {
  total: number;
  completed: number;
  inProgress: number;
  todo: number;
  blocked: number;
} {
  return {
    total: tasks.length,
    completed: tasks.filter(t => t.status === "done").length,
    inProgress: tasks.filter(t => t.status === "in_progress").length,
    todo: tasks.filter(t => t.status === "todo").length,
    blocked: tasks.filter(t => t.status === "blocked").length,
  };
}
```

**验收标准**:
- 正确读取 tasks.json
- 正确映射状态
- 导出 `readLocalTasks()` 和 `calculateProjectProgress()`

---

### piv_002: 修改 snapshot-store.ts

**文件**: `src/runtime/snapshot-store.ts`

**功能**: 使用本地任务数据**覆盖** Gateway 数据

**代码量**: 40 行修改

**实现**:
```typescript
import { readLocalTasks, calculateProjectProgress } from "./task-local-reader";

export async function saveSnapshot(next: ReadModelSnapshot): Promise<SnapshotStoreResult> {
  const prev = await readPreviousSnapshot();

  // ✅ 核心修改：使用本地任务数据覆盖 Gateway 数据
  const localTasks = await readLocalTasks();
  if (localTasks && localTasks.tasks && localTasks.tasks.length > 0) {
    // 完全覆盖 Gateway 的任务数据
    next.tasks = {
      tasks: localTasks.tasks,
      agentBudgets: localTasks.agentBudgets || [],
      updatedAt: localTasks.updatedAt || new Date().toISOString(),
    };

    // 重新计算 tasksSummary
    const progress = calculateProjectProgress(localTasks.tasks);
    next.tasksSummary = {
      projects: new Set(localTasks.tasks.map(t => t.projectId)).size,
      tasks: progress.total,
      todo: progress.todo,
      inProgress: progress.inProgress,
      blocked: progress.blocked,
      done: progress.completed,
      owners: new Set(localTasks.tasks.map(t => t.owner)).size,
      artifacts: 0,
    };
  }

  const diff = computeDiff(prev, next);

  await mkdir(dirname(LAST_SNAPSHOT_PATH), { recursive: true });
  const tempPath = `${LAST_SNAPSHOT_PATH}.tmp-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  await writeFile(tempPath, JSON.stringify(next, null, 2), "utf8");
  await rename(tempPath, LAST_SNAPSHOT_PATH);

  return {
    path: LAST_SNAPSHOT_PATH,
    diff,
  };
}
```

**验收标准**:
- 本地任务数据**完全覆盖** Gateway 数据
- `tasksSummary` 正确计算
- last-snapshot.json 包含正确的任务数据

---

### piv_003: 修改 monitor.ts

**文件**: `src/runtime/monitor.ts`

**功能**: 禁用 Gateway 任务同步

**代码量**: 10 行修改

**实现**:
```typescript
export async function runMonitorOnce(adapter: OpenClawReadonlyAdapter): Promise<void> {
  const snapshot = await adapter.snapshot();

  // ✅ 清除 Gateway 返回的任务数据（使用本地数据）
  snapshot.tasks = { tasks: [], agentBudgets: [], updatedAt: '' };
  snapshot.tasksSummary = {
    projects: 0,
    tasks: 0,
    todo: 0,
    inProgress: 0,
    blocked: 0,
    done: 0,
    owners: 0,
    artifacts: 0,
  };

  const stored = await saveSnapshot(snapshot);
  const alerts = commanderAlerts(snapshot);
  const digest = await writeCommanderDigest(snapshot, alerts);
  const heartbeat = await runTaskHeartbeat();
}
```

**验收标准**:
- Gateway snapshot 的任务数据被清除
- `saveSnapshot()` 使用本地任务数据

---

### piv_004: 测试数据合并

**文件**: `tests/task-local-reader.test.ts` (新建)

**功能**: 单元测试

**代码量**: 100 行

**测试用例**:
```typescript
import { readLocalTasks, calculateProjectProgress } from "../src/runtime/task-local-reader";

describe("Task Local Reader", () => {
  test("readLocalTasks() 应该读取 tasks.json", async () => {
    const tasks = await readLocalTasks();
    expect(tasks).not.toBeNull();
    expect(tasks.tasks).toBeDefined();
  });

  test("状态映射应该正确", async () => {
    const tasks = await readLocalTasks();
    expect(tasks.tasks[0].status).toBe("done"); // completed → done
  });

  test("calculateProjectProgress() 应该正确计算进度", () => {
    const tasks = [
      { status: "done" },
      { status: "done" },
      { status: "in_progress" },
    ];
    const progress = calculateProjectProgress(tasks);
    expect(progress.total).toBe(3);
    expect(progress.completed).toBe(2);
    expect(progress.inProgress).toBe(1);
  });
});
```

**验收标准**:
- 所有测试通过
- 覆盖率 > 80%

---

### piv_005: 集成测试

**文件**: `tests/integration/snapshot-store.test.ts` (新建)

**功能**: 集成测试

**代码量**: 80 行

**测试用例**:
```typescript
import { saveSnapshot } from "../src/runtime/snapshot-store";
import { writeFileSync } from "fs";
import { join } from "path";

describe("Snapshot Store Integration", () => {
  beforeEach(() => {
    // 准备测试数据
    const testTasks = {
      tasks: [
        {
          taskId: "test_001",
          projectId: "test-project",
          title: "测试任务",
          status: "completed",
          owner: "coder",
        },
      ],
    };
    writeFileSync(join(process.cwd(), "runtime", "tasks.json"), JSON.stringify(testTasks));
  });

  test("saveSnapshot() 应该使用本地任务数据", async () => {
    const gatewaySnapshot = {
      tasks: { tasks: [], agentBudgets: [], updatedAt: '' },
      tasksSummary: { tasks: 0, done: 0, ... },
      // ... 其他字段
    };

    const result = await saveSnapshot(gatewaySnapshot);

    // 读取 last-snapshot.json
    const saved = JSON.parse(readFileSync(result.path, "utf8"));
    expect(saved.tasks.tasks.length).toBe(1);
    expect(saved.tasks.tasks[0].status).toBe("done");
    expect(saved.tasksSummary.done).toBe(1);
  });
});
```

**验收标准**:
- 集成测试通过
- 验证本地数据覆盖 Gateway 数据

---

### piv_006: 手动测试

**测试步骤**:

1. **准备数据**：
   ```bash
   # 更新 tasks.json
   echo '{"tasks":[{"taskId":"test_001","projectId":"test","title":"测试","status":"completed","owner":"coder"}]}' > runtime/tasks.json
   ```

2. **运行 Evolver 同步**：
   ```bash
   cd ~/.openclaw/evolver
   npm run control-center-sync
   ```

3. **检查 last-snapshot.json**：
   ```bash
   cat runtime/last-snapshot.json | grep -A 10 "tasksSummary"
   # 应该显示: tasks: 1, done: 1
   ```

4. **刷新 Control Center UI**：
   - 浏览器访问 http://127.0.0.1:4310
   - 强制刷新 (Ctrl+F5)
   - 检查任务状态和项目进度

5. **验证**：
   - ✅ 任务状态：1 个已完成
   - ✅ 项目进度：100%
   - ✅ tasksSummary: { tasks: 1, done: 1 }

**验收标准**:
- UI 显示正确的任务状态
- 项目进度正确
- 多次刷新保持一致

---

## 数据流设计

### 旧数据流（有问题）

```
Gateway (旧数据) → monitor → saveSnapshot (合并) → UI (错误)
```

### 新数据流（正确）

```
Gateway (无任务) → monitor (清除任务) → saveSnapshot (用本地覆盖) → UI (正确)
     ↑
     └─ tasks.json (唯一数据源)
```

---

## 技术方案

### 核心修改

1. **task-local-reader.ts** (新)：
   - 读取本地 tasks.json
   - 映射状态
   - 计算进度

2. **snapshot-store.ts** (修改)：
   - **覆盖**而不是合并
   - 使用本地任务数据

3. **monitor.ts** (修改)：
   - 清除 Gateway 的任务数据
   - 确保使用本地数据

---

## 测试策略

### 单元测试

- `readLocalTasks()` - 读取文件
- `mapTaskStatus()` - 状态映射
- `calculateProjectProgress()` - 进度计算

### 集成测试

- `saveSnapshot()` - 本地数据覆盖 Gateway
- last-snapshot.json 内容验证

### 手动测试

- UI 显示验证
- 多次刷新一致性
- Evolver 同步验证

---

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| tasks.json 格式错误 | 中 | 添加错误处理，返回 null |
| Gateway 其他数据丢失 | 低 | 只清除任务，保留会话、Cron 等 |
| UI 缓存问题 | 低 | 强制刷新，清除缓存 |

---

## 回滚计划

**如果出问题**：
```bash
git checkout HEAD~1 -- src/runtime/snapshot-store.ts
git checkout HEAD~1 -- src/runtime/monitor.ts
rm src/runtime/task-local-reader.ts
```

---

## 时间估算

| piv | 预估时间 |
|-----|---------|
| piv_001 - task-local-reader.ts | 1 小时 |
| piv_002 - snapshot-store.ts | 1 小时 |
| piv_003 - monitor.ts | 0.5 小时 |
| piv_004 - 单元测试 | 1 小时 |
| piv_005 - 集成测试 | 0.5 小时 |
| piv_006 - 手动测试 | 0.5 小时 |
| **总计** | **4.5 小时** |

---

_创建时间: 2026-03-19 16:29_
