# PLAN: 审查流 + 意图准入 + 最近产出快照（review-pipeline）

## Context

用户实测暴露三病灶（2026-08-16 23:18 日志铁证）：
1. **问句触发生成**："配套明细表还需要补充吗"（问句）→ `_detect_draft_complete` 复合检测命中"补充"+"工艺文件" → 0.85 置信度**无条件覆盖** LLM/关键词结果（intent_recognizer.py:148-155, :272-310）→ draft_complete → 11 章重生成。对话问了句话，文件被重写。
2. **review 无真实执行器**：review_document 意图存在但落不到事实对照，LLM 用通识自造"核心模块"标准瞎评（"缺少工艺装备表"——实际源文档全有）。
3. **"刚才生成的那篇"无实体**：state 记"在干什么"不记"产出物"，新会话指代失败（"未找到初稿"）。

用户拍板的规则（ALIGN 已 seal，模糊点清零）：
- **准入红线**：生成/补齐只从按钮（generation_mode）触发，**对话入口永不触发生成**
- 意图分类：审查 / 修改 / 问答（后续可扩展）
- 修改意图在同事执行单元合入前 = 安全兜底（"功能建设中"回复，不碰文件）
- review 四对照一次做全（模板/DB/内容质量/需求覆盖——前三机器算，LLM 只做第四且只能引用事实清单）
- 快照只存最近一次产出

分支 `feature/review-pipeline`（已建，ALIGN 已 seal 两 commit）。

## 改动清单（6 节点）

### N1 意图识别修复 + 问句闸门（23:18 根因）

| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/orchestrator/intent_recognizer.py` | ① `_detect_draft_complete` 加**问句闸门**：输入含问句特征（`吗|呢|？|需不需要|有没有|是不是|还需不需要`收尾结构）→ 复合检测返回 0.0（问句永不是补全指令）。② LLM 分类 prompt（:196-208）补审查问法示例（"有什么问题/还需要补充吗/缺什么"→ review_document；一般咨询 → search_knowledge/qa）。③ `unknown` 不再静默走 draft_analysis——返回带 `needs_clarification` 标记 |
| `backend/tests/test_intent_recognizer.py` | 新用例：问句+补充+文件 → 非 draft_complete；"有什么问题吗"→ review；unknown → needs_clarification |

### N2 对话入口准入守卫（红线，防未来回归）

| 文件 | 改什么 |
|------|--------|
| `backend/app/api/agent.py` | generate-stream 里（generation_mode shortcut 处 :507 对应的 orchestrator 侧路径）：**orchestrator 只在 `context["generation_mode"] in (generate, fill)` 时进 draft_complete**——draft_complete 意图从对话识别（非 shortcut）进来时，检查无 generation_mode → 不执行，返回澄清回复。守卫逻辑放 orchestrator `process_intent` 的 draft_complete 分支入口（:523/:534 两处），一处函数化 `_gate_draft_complete(intent, context)` |
| `backend/tests/test_orchestrator_state_all_paths.py`（扩展） | 对话文本识别为 draft_complete 但无 generation_mode → 不进 executing；带 generation_mode → 正常进 |

### N3 最近产出快照

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/project_state_service.py` | schema 加第 8 字段 `last_output`：`{"updated_at", "chapters": [{"code","title","rows"}], "warnings_count"}`（摘要级，不含全量数据——全量在前端/编辑器）。`update_from_turn` 加可选参数 `output_summary` |
| `backend/app/api/agent.py` | `_persist_turn`（:1633）加 `output_summary` 参数，template 产出路径（structured_results 非空处）传章节摘要；QA/review 的 `_build_orchestrator_context` 把 `last_output` 渲染进 state 块（"最近产出：9 章已生成 G4a/G5a/…，3 处警告"） |
| `backend/tests/test_project_state_service.py` | last_output 写读回环 + 渲染进块 |

### N4 review-pipeline 四对照执行器（核心新件）

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/review_pipeline.py`（新） | `run_review(project_state, structured_results_or_none, template_id, user_input, db) -> {"issues": [...], "summary": str}`。四对照：<br>① **模板对照**：`template_loader.get_chapters(load_template("assembly_process_cable"))` 章节 code 集 − 已生成 code 集 = 缺章清单（机器算）<br>② **DB 有据**：生成内容里的材料名/标准号 → `knowledge_search.find_material_by_code` + name 查（复用 G18a enrich 模式），查无报"无据"提示级<br>③ **内容质量**：扫 filled_data 空格子 / "待补"占位 / warnings（degraded 行）——G25a warnings 推广到全章节<br>④ **需求覆盖**（唯一 LLM）：输入 = 用户原始需求 + ①②③ 的事实清单，prompt 硬约束"只能引用清单内容，禁止基于通识评估，无对照材料时明说"——tier=simple<br>issues 分级 `severity: critical(缺章)/warn(空格·无据)/info`，每条带 `source`（哪个对照产出） |
| `backend/tests/test_review_pipeline.py` | mock structured_results + tmp DB：缺章检测 / 空格扫描 / 有据无据 / summary 生成（LLM mock） |

### N5 意图路由接执行器

| 文件 | 改什么 |
|------|--------|
| `backend/app/api/agent.py` | draft_complete 之外的分支：`review_document` 意图 → 取 state 的 last_output（无则取上传文件摘要）→ `run_review` → 结果渲染成分级清单 SSE `content` 事件（复用现有 content 事件流，纯文本回复不碰编辑器）；`edit_document` 意图 → 安全兜底回复（"修改功能建设中…"）；qa → 现有 QA 路径 + state 块已含 last_output 摘要 |
| `backend/tests/app/api/test_agent_review_routing.py` | review 意图走 run_review 不进 executing；edit 意图返回兜底文案；日志断言无 chapters_parallel |

### N6 收尾

| 文件 | 改什么 |
|------|--------|
| `ARCHITECTURE.md` + `DEV-LOG.md` | §2 Agent 系统补 review-pipeline 执行器 + 意图准入闸门；§4 补 last_output 快照 |

## 禁区

- 不碰：生成/补齐主链本体（shortcut 路径零改动——守卫只挡"对话识别出的 draft_complete"，不挡 generation_mode）、同事的 edit 执行单元（只留路由兜底）、"来自何处"列、前端大改
- review 回复**纯聊天文本**（SSE content 事件），不触发 editor_content / template_data——审查不动文件
- `_detect_draft_complete` 的 generation_mode 快捷路径（orchestrator :507）行为不变

## 验证

- 每节点单测（模式同前：monkeypatch + AsyncMock）
- 全量门：`cd backend && python -m pytest tests -q --deselect "...test_prompt_requires_step_name_prefix"` ≥ 871 passed 0 新失败
- **场景回归（对着 23:18 事故）**：mock 链路重放"生成的工艺文件，配套明细表还需要补充吗"+uploaded_file → 断言：intent=review、零 executing_chapters、回复含对照事实（非通识）、state.last_output 更新
- 留部署环境：真实本地模型下 review 问句的意图识别准确率、四对照实际效果观感

## 风险与缓解

- 问句闸门误伤真补全指令（"补充一下工序五"命令式无问句特征）→ 闸门只匹配问句结构（吗/？收尾），命令式不受影响；用例覆盖两种
- last_output 摘要过大 → 只存 code/title/rows 计数 + warnings 计数，不存数据本体
- DB 对照慢 → 只查材料名/标准号字段，批量 IN 查询，超 20 条截断加"部分核对"标注
