# 需求对齐卡：清理 document_generator 死代码

> slug: `cleanup-docgen-deadcode` · 软，可改，不 seal

## 背景（已确认死代码）
web 验收发现 `tool_not_found document_generator` warning。深挖确认：
- document_generator **没注册**（discover_tools 没触发 document_tool 的 @register）
- `generate_doc` 全 False（orchestrator 5 处）+ process 唯一调用方（orchestrator:3702）是死回退（走 handle_feedback，process 永不执行）
- use_tool tool=None 返回 success=False（不抛错）→ 即使触发也无害
- document_tool.py + document_generator.py 只被自身 + 测试引用，生产零调用
- 被 `_do_template_fill` 取代（generate-stream 走它，不走 process use_tool）

## 目标
- 删 document_generator 相关死代码，消除 tool_not_found warning（日志噪声 + 误导排查）+ 减负
- 成功：启动无 tool_not_found document_generator warning + pytest 回归无新 fail + web 生成不受影响

## 边界
- **做**：删 document_tool.py + document_generator.py + writing_agent.py 的 tools 声明/use_tool 段/return document 字段 + app/tools/__init__.py 引用 + 相关测试
- **不做**：不动 `_do_template_fill`（取代者）/ `handle_feedback` / process 主体（只删 document_generator 段）/ 其他 agent 的 use_tool

## 模糊点
- `tests/validation/accuracy_tests.py:21` import DocumentTool（validation 手动验收脚本，可能整体过时）—— 删 import；若脚本还用 DocumentTool 实例则它早已坏（document_generator 没注册），记录为过时脚本不动其逻辑
- writing_agent.process 的 return `document` 字段去除后，下游（process 调用方 3702 死回退）无消费者，安全

## 下游
- → 进 PLAN（同 slug `cleanup-docgen-deadcode`）
