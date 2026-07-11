# PLAN: 清理 document_generator 死代码

> slug: `cleanup-docgen-deadcode` · 承接 `ALIGN-cleanup-docgen-deadcode.md` · seal 后不可变

## Context

web 验收发现 `tool_not_found document_generator` warning。深挖确认 document_generator 是死代码：没注册 + generate_doc 全 False + process 唯一调用方是死回退 + 被 _do_template_fill 取代 + 生产零调用（见 ALIGN 证据链）。清理以消除 warning（日志噪声 + 曾误导验收排查）+ 减负。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/functional/writing_agent.py` | ① `:59` `tools = ["document_generator"]` → `tools = []`（消除 tool_not_found warning）。② `:152-162` 删 `generate_doc` use_tool document_generator 段。③ `:164-176` return 去 `document`/`has_document` 字段（doc_result 已删，下游 3702 死回退无消费者） |
| `backend/app/tools/document_tool.py` | **删整个文件**（DocumentTool，死代码） |
| `backend/app/tools/document_generator.py` | **删整个文件**（DocumentGenerator，只被 document_tool.py:56 import，孤儿） |
| `backend/app/tools/__init__.py` | 删 `:50` `from .document_generator import ...` + `:77` tool_modules 列表的 `"document_tool"` |
| `backend/tests/app/tools/test_tools.py` | 删 DocumentTool 相关测试类（test_document_tool_*，7 处） |
| `backend/tests/validation/accuracy_tests.py` | `:21` 删 `from app.tools.document_tool import DocumentTool`（若脚本后文用，记录为过时脚本，不动逻辑） |

## 禁区

- `_do_template_fill`（取代者，generate-stream 主路径）
- `handle_feedback`（process 的取代者）
- writing_agent.process 主体（action 路由 edit/fill/format/generate 保留，只删 document_generator 段）
- 其他 agent（proofread/review）的 use_tool（用 terminology/compliance，不涉及）
- generation_state.py:178 `"formatter": "process_document_generator"`（字符串值，不相关，不动）

## 验证

1. `cd backend && python -m pytest tests/ -q`（回归无新 fail；test_tools 删 document_tool 测试后总数下降属正常）
2. 启动后端，日志**无** `tool_not_found document_generator`
3. web 回归：project=2 generate 模式生成，G25a/G18a 正常（document_generator 不在生成路径，应无影响）
4. grep 确认无残留：`grep -rn "document_generator\|DocumentTool" backend/app/`（应只剩 generation_state.py:178 的不相关字符串）

## 节点拆分

1. **节点1**：writing_agent.py（tools 声明 + use_tool 段 + return）+ 删 document_tool.py/document_generator.py + __init__.py（commit `refactor`）
2. **节点2**：测试清理（test_tools.py + accuracy_tests.py）+ 全量回归 + 启动验无 warning（commit `chore`）

## 执行约定

- seal：本文件 git commit `plan: cleanup-docgen-deadcode seal`
- 简单直接改（机械删，每节点多文件但无设计决策）
- 出错暂停
