---
description: Execute a development plan with full Archon task management integration
argument-hint: [plan-file-path]
---

# Execute Development Plan

> 详细流程索引: `.claude/skills/execute-plan/index.md`

## 快速参考

| 步骤 | 名称 | 指令文件 |
|------|------|----------|
| 1 | 读取解析计划 | `steps/step-1-read-plan.md` |
| 2 | Archon项目设置 | `steps/step-2-project-setup.md` |
| 3 | 创建所有任务 | `steps/step-3-create-tasks.md` |
| 4 | 代码库分析 | `steps/step-4-codebase-analysis.md` |
| 5 | 实现循环 | `steps/step-5-implementation.md` |
| 6 | 验证阶段 | `steps/step-6-validation.md` |
| 7 | 最终化任务 | `steps/step-7-finalize.md` |
| 8 | 最终报告 | `steps/step-8-report.md` |

## 核心约束

- **文件操作**: `.claude/constraints/file-operations.md`
- **验证策略**: `.claude/constraints/validation.md`
- **Token优化**: `.claude/constraints/token-optimization.md`

## 工作流规则

1. **必须**使用 Archon 任务管理
2. **必须**预先创建所有任务
3. **保持**单一任务 "doing" 状态
4. **验证**后再标记 "done"
5. **保存**进度到 `.claude/progress/`

## 进度保存

每步完成后更新:
```
.claude/progress/current-state.json
```

## 执行流程

根据当前步骤，加载对应指令:
```
.claude/skills/execute-plan/steps/{{current_step}}.md
```
