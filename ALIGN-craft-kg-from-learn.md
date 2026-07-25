# 需求对齐卡：学习为画像 → 灌 craft KG（+文件夹批量）

## 背景（问题怎么来的）

`g25a-method-aux-bind` 的 N1 做了全局 craft KG 的「壳」（`load_craft_kg`/`save_craft_kg`/全局实例 `craft_kg`/启动 `init_craft_kg`），但**全代码库 `save_craft_kg` 零调用、无 seed、无灌数据链路** → `craft_kg` 永远空图 → N3 `_search_knowledge_graph` 被 `node_count>0` 守卫跳过（hierarchical_context.py:975）→ `aux_standards` 永远空 → N5 生成时辅料参数标准段永远不注入（writing_agent:1629 `if aux_standards else ""` 走空分支）。**N3 整层（辅料-参数标准关联）实际空跑**，这是 N1 规划漏洞（壳做了，N1-N6 没安排谁填数据）。

用户定：走 **A**（从已 extract 的 triples/graph 灌），触发点接「学习为画像」按钮——learn 产出 triples/graph 时同步灌进 `craft_kg` + `save_craft_kg`。按钮增强**文件夹选取**（批量）。**C**（全量自动灌入 extract 链路）留后续。

## 目标

把「学习为画像」从「只存 `Profile.graph`（per-domain 画像）」扩成「**同时灌 `craft_kg`（全局）+ 持久化**」，让 N3 有数据可查；按钮支持文件夹批量。

### 成功标准（可观察）

- 点「学习为画像」后：`craft_kg.node_count > 0` + `data/knowledge_graph.json` 文件生成（有 nodes/edges）。
- N3 `_search_knowledge_graph` 对工序/辅料实体**真返回内容**（不再被空图守卫跳过）。
- 文件夹批量：选文件夹 → 逐文件 learn + 灌 KG，全部并入 craft_kg。
- 不破坏现有 `Profile.graph` per-domain 画像（learn 原逻辑保留，只是多灌一份到全局）。

## 边界

### 做
- profile learn 后端 handler（`/api/profile/{domain}/learn`）成功后加一步：triples/graph → 合并进 `craft_kg` → `save_craft_kg`。
- 前端「学习为画像」按钮支持文件夹选取（批量触发）。
- 合并语义：累加幂等（networkx `add_node` 天然幂等）。

### 不做
- 不改 `KnowledgeExtractor`（`/api/knowledge/extract/document` 物料落库链路）——那是 C，后续。
- 不改 N3 查询逻辑（craft_kg 有数据后自然生效）。
- 不动其他 source-driven 章节（G4a/G5a/G18a/G12a/G14a/G22a）。
- 不一次性人工录大辅料参数库。

## 已定决策（2026-07-25 对齐，模糊点清零）

1. **数据源 = triples**（技术定）：查 `learn_from_content`(document_profile_learner.py:47-79) 只产 triples、**不产 graph**——graph 字段 learn 从不填，我之前提的"graph 优先"撤回。灌 KG 走 `triples → build_from_triples() → 合并 craft_kg → save_craft_kg`。`build_from_triples`(knowledge_graph.py:239) 现场建 KG 与 graph 预存结构等价（都是 nodes/edges），N3 查节点边不分来源 → **够用**。
2. **文件夹批量 = 后端新端点 + SSE 进度**（用户定）：后端加批量 learn 端点（吃 dir_name），进度走 SSE 流式推送（每文件完成推 `X/N + 当前文件名`）。模式现成——**localkb 自己生成流程已用 SSE（复用对口）**，Journalist 副本印证同款（agent.py:177 StreamingResponse + transcribe.py DB progress 双模式）。
3. **domain 隔离 = 先不做**（用户定）：craft_kg 跨 domain 累加合并；N3 暂不按 domain 过滤，看实际效果再定。
4. **重复 learn = 累加幂等**（默认）：networkx `add_node` 天然去重，不搞先移旧节点。
5. **衔接点**：PlanMode 读 `/api/profile/{domain}/learn` handler 确认 features 持久化与否，定灌 KG 步骤挂 handler 还是 learner。

## 下游
- → 进 PLAN（同 slug `craft-kg-from-learn`）
- PLAN 第一步：读 `/api/profile/{domain}/learn` handler + `document_profile_learner` 确认 triples/graph 产出与持久化点，定衔接位置。
