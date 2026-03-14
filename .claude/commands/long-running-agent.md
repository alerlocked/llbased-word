---
description: Execute long-running agent tasks with proper state management and Archon integration
argument-hint: [task-description-or-feature-name]
---

# Long-Running Agent Execution

> 详细流程索引: `.claude/skills/long-running-agent/index.md`

## 快速参考

| 步骤 | 名称 | 指令文件 |
|------|------|----------|
| 1 | 初始化/恢复状态 | `steps/step-1-init.md` |
| 2 | 状态恢复 | `steps/step-2-recovery.md` |
| 3 | 任务选择 | `steps/step-3-selection.md` |
| 4 | 实现 | `steps/step-4-implementation.md` |
| 5 | 验证 | `steps/step-5-validation.md` |
| 6 | 进度更新 | `steps/step-6-progress.md` |
| 7 | Git提交 | `steps/step-7-commit.md` |

## 核心约束

- **文件操作**: `.claude/constraints/file-operations.md`
- **验证策略**: `.claude/constraints/validation.md`

## 进度保存

- `.claude/progress/current-state.json`
- `.claude/progress/feature-list.json`

## 执行流程

根据当前步骤，加载对应指令:
```
.claude/skills/long-running-agent/steps/{{current_step}}.md
```

## 成功标准

- 功能实现 ≥97% 准确性
- 所有测试通过
- 代码可合并状态
- 进度正确保存
