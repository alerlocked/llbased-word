# Create Implementation Plan - 索引

> 完整流程见: `.claude/skills/create-plan/full-workflow.md`

## 快速参考

| 步骤 | 名称 | 详细指令 |
|------|------|----------|
| 1 | 读取分析需求 | `steps/step-1-requirements.md` |
| 2 | 研究阶段 | `steps/step-2-research.md` |
| 3 | 规划设计 | `steps/step-3-planning.md` |
| 4 | 创建计划文档 | `steps/step-4-document.md` |
| 5 | 验证计划 | `steps/step-5-validation.md` |

## 输出

计划文件保存到: `PRPs/requests/[feature-name].md`

## 核心约束

- 文件操作: `.claude/constraints/file-operations.md`
- Token优化: `.claude/constraints/token-optimization.md`

## 加载对应指令

```
根据当前步骤，读取: .claude/skills/create-plan/steps/{{current_step}}.md
```
