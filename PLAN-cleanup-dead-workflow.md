# PLAN: 清理 orchestrator 死 workflow 链路 + 修 ARCHITECTURE 文档腐烂

> slug: `cleanup-dead-workflow`(总纲 `dialog-task-pipeline` 第一步)
> seal 后不可变。Reviewer 从 git 读本文件。

## Context(为什么改)
对话任务分配链路调研发现:`orchestrator.py` 的 workflow 编排链路(`_select_workflow` / `execute_workflow` / `workflows` 字典 / 4 个 workflow)是**死代码**——全 backend 业务代码零调用,实际任务调度走 `_dispatch_to_sub_agent`(:674)。但 `ARCHITECTURE.md` §2 仍把这 4 个 workflow 当活的写,误导接手(文档腐烂)。

这是 `dialog-task-pipeline` 总纲的**第一步**:动手改调度/意图识别前,先扫掉死代码 + 让架构文档对齐代码。不影响 generate/fill 补齐主链(死代码不在主链上)。基于现有功能,只删不重写。

## 改动清单

| 文件:行 | 改什么 |
|---------|--------|
| `backend/app/agents/orchestrator/orchestrator.py:297-303` | 删 `# 工作流配置` 注释 + `self.workflows = {...}` 字典 |
| `backend/app/agents/orchestrator/orchestrator.py:779-806` | 删 `_select_workflow()` 方法整体(零调用) |
| `backend/app/agents/orchestrator/orchestrator.py:808-916` | 删 `execute_workflow()` 方法整体(零调用);profile/review/rollback 逻辑在 `_dispatch_to_sub_agent` 已覆盖或不适用 |
| `ARCHITECTURE.md:24` | 删 `- **Workflows**:full_edit[...] / quick_edit[...] / review_only[...] / proofread_only[...]。` 整行 |

## 禁区(保留,勿删)
- ⚠️ `orchestrator.py:3636` `proofread_only()` + `:3667` `review_only()` **活的方法**(task.py:543/582 调用),与死 workflow 字典 key 同名但不同物,绝不删。
- `agents/core/registry.py:303-325` `WorkflowRegistry`(业务零调用但 test_registry 依赖),本次不动,留下一步评估。
- `ARCHITECTURE.md:21-22` 功能 Agent 描述、generate/fill 补齐主链:零改动。

## 验证
1. `cd backend && pytest` 全量回归(基线 ~763 passed,0 新 failed;重点 `test_orchestrator_interactive.py::test_proofread_only/test_review_only` 仍过)。
2. `grep -rn "self\.workflows\|_select_workflow\|execute_workflow" backend/app` → app/ 下零残留。
3. `ARCHITECTURE.md` §2 校对。

## 下游
验证通过 + commit 后,回 `ALIGN-dialog-task-pipeline` 总纲对齐第二步。
