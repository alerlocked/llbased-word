# 需求对齐卡：完整生成测试暴露的后端问题分批处理

## 背景
2026-07-19 09:44 一次完整生成测试（documents/1，11 章），后端日志诊断暴露 4 个问题。本卡对齐这批问题的**处理范围、顺序、定性**。

## 目标
- **解决谁的什么问题**：让"完整生成"后端链路健康、可观测、无静默缺陷
- **成功长什么样（可观察）**：
  - `curl /health` 返回 200 且秒回（不再 404 + 67s）
  - 日志不再被 sqlalchemy SQL echo 刷屏
  - G5a/G12a/G14a 数据偏低**根因定位**（真 bug→修；已知债务→明确归档，不混入本期）
  - 生成期间事件循环阻塞**根因定位** + 是否修的决策落地（修或记债务都算处理）

## 边界
- **做**：4 个问题的诊断 + 真 bug 的最小修复
- **不做**：
  - 不重构生成架构（除非 #4 诊断后用户拍板）
  - 不动前端
  - 不加新功能
  - **不逐章提质 G14a/G12a**（那是 [[exp-generation-debugging]] §1.9/§4 的 open item，独立 lead；本期只"定性+归档"）

## 待处理清单（4 项）

| # | 问题 | 根因状态 | 性质 |
|---|------|---------|------|
| 1 | G5a `ref_name=1` / G12a `quota=1` / G14a `material_desc=0` | 待诊断 | **疑似已知债务**（exp §1.9 各章节单薄），非必然新 bug |
| 2 | `/health` 404 | 已确认：`main.py:301` `mount("/",...)` 注册在 `@app.get("/health")`(318) 之前 | 真 bug，小修（路由顺序） |
| 3 | sqlalchemy SQL echo 刷屏 | 已确认：config `echo=True` | 小修（echo=False） |
| 4 | 生成期事件循环阻塞 67s（/health 排队等生成结束） | 半确认：LLM 同步调用未 offload | 架构，**PMF 判断** |

## 模糊点
- **[待诊断]** `structured_extraction_done` 的 `fields_found` 是 **extract 源文档**结果还是 **LLM 生成结构化**结果？→ 决定 G14a `material_desc=0` 是 extract 漏抽（bug）还是 LLM 单薄（已知债务）
- **[待诊断]** G5a `ref_name=1`：源只有 1 行 vs extract 漏抽（[[exp-fileref-source-extract]] colspan 表头动态映射陷阱）
- **[待用户拍板]** #4 事件循环阻塞：PMF 阶段单用户工具，值不值得现在动架构？→ 先诊断根因，再用三段式上报让用户拍
- **[接受的不确定性]** G12a/G14a 若定性为"LLM 生成单薄"已知债务 → 本期只归档，不逐章提质（独立 lead）
- **[接受的不确定性]** 处理顺序 = 诊断(#1) → 小修打包(#2+#3) → 架构(#4 单独评估)

## 下游
- → 进 PLAN（slug=`gen-test-fixes`），**诊断结果回填模糊点后才 seal**
- 诊断在 PlanMode（只读）完成：`diagnose_all_chapters.py` 跑 #1 + grep 定位 #4 同步调用点 + Read 确认 #2#3 改点
