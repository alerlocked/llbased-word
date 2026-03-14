# Execute Development Plan - 索引

> 完整流程见: `.claude/skills/execute-plan/full-workflow.md`

## 快速参考

| 步骤 | 名称 | 详细指令 |
|------|------|----------|
| 1 | 读取解析计划 | `steps/step-1-read-plan.md` |
| 2 | Archon项目设置 | `steps/step-2-project-setup.md` |
| 3 | 创建所有任务 | `steps/step-3-create-tasks.md` |
| 4 | 代码库分析 | `steps/step-4-codebase-analysis.md` |
| 5 | 实现循环 | `steps/step-5-implementation.md` |
| 6 | 验证阶段 | `steps/step-6-validation.md` |
| 7 | 最终化任务 | `steps/step-7-finalize.md` |
| 8 | 最终报告 | `steps/step-8-report.md` |

## 当前状态

```yaml
任务类型: {{task_type}}
当前步骤: {{current_step}}
项目ID: {{project_id}}
```

## 核心约束

- 约束文件读取: `.claude/constraints/file-operations.md`
- 验证策略: `.claude/constraints/validation.md`
- Token优化: `.claude/constraints/token-optimization.md`

## 加载对应指令

```
根据当前步骤，读取: .claude/skills/execute-plan/steps/{{current_step}}.md
```
