# Step 5: 实现循环

## 子步骤

### 5.1 开始任务
```
mcp__archon__manage_task("update", status="doing")
```

### 5.2 实现
- 执行实现
- 确保代码质量

### 5.3 完成任务
```
mcp__archon__manage_task("update", status="review")
```

## 规则

**同时只有一个任务处于 "doing" 状态**

## 进度保存

每次完成后更新: `.claude/progress/current-state.json`
