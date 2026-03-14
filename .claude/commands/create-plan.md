---
description: Create a comprehensive implementation plan from requirements document through extensive research
argument-hint: [plan-description-or-requirements-file]
---

# Create Implementation Plan

> 详细流程索引: `.claude/skills/create-plan/index.md`

## 快速参考

| 步骤 | 名称 | 指令文件 |
|------|------|----------|
| 1 | 读取分析需求 | `steps/step-1-requirements.md` |
| 2 | 研究阶段 | `steps/step-2-research.md` |
| 3 | 规划设计 | `steps/step-3-planning.md` |
| 4 | 创建计划文档 | `steps/step-4-document.md` |
| 5 | 验证计划 | `steps/step-5-validation.md` |

## 核心约束

- **文件操作**: `.claude/constraints/file-operations.md`
- **Token优化**: `.claude/constraints/token-optimization.md`

## 输出

计划保存到: `PRPs/requests/[feature-name].md` (500-1000行)

## 执行流程

根据当前步骤，加载对应指令:
```
.claude/skills/create-plan/steps/{{current_step}}.md
```

## 完成后

```
Implementation plan created at: PRPs/requests/[feature-name].md
Execute with: /execute-plan PRPs/requests/[feature-name].md
```
