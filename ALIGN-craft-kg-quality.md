# 需求对齐卡：craft KG 质量改进（规格识别 + 节点类型 + 检索匹配）

## 背景（为什么做）
2026-07-26 端到端验证（开发机云端 qwen3-30b-a3b）发现：craft_kg 灌了数据（learn→triples，10 nodes）但**贡献小**——G25a 真生成时 `g25a_aux_injected has_aux=true` **主要靠 DB knowledge_search**（MaterialCatalog/StandardClause），KG 部分（craft_kg expand）匹配弱（`_search_knowledge_graph` seed_ids 模拟=[]）。即"壳接通了、数据灌了，但检索时 KG 节点查不到"。

三件相关待办（TODO 7a 实证，commit 3c0c2a3 之后）：
- **① 7a③ 规格识别扩展**：`_extract_triples` 抽到 M4 螺柱→力矩1.9，但 **M5 螺柱3.6N·m 漏抽**（content.html 里"螺柱 M5 8 A2-70"拆散表述 pattern 覆盖不到）+ **GB/T 标准号没作 subject**（GB/T68-2000 关联力矩/参数）。
- **② 7a② 节点类型**：`build_from_triples` 把所有 subject 全标 `process_step`（M4 螺柱也是），该按 subject 判标 [规格]/[材料]/[工序]。type 标错误导下游检索/展示。
- **③ craft_kg 匹配度**：`_search_knowledge_graph(query=G25a 工序名)` → `extract_keywords`(装配/准备/密封圈) 匹配 KG 节点 label（M4 螺柱/泛词工序），**两维度不同**（工序名 vs 规格/参数），匹配弱。

## 目标
让 craft_kg 真正贡献 G25a 辅料标准关联（`has_aux` 来自 KG 不只靠 DB）。

## 成功标准（可观察）
- learn 装配素材后 craft_kg 有**规格节点**（M5 螺柱 / GB/T 标准号）+ 类型标对（spec/material，非全 process_step）
- 真生成 G25a 时 `_search_knowledge_graph` 的 **KG 部分**（craft_kg expand）非空——日志可见 KG 节点被 seed 命中（不只 DB 部分）
- 不回归：现有 triples 抽取（温度/压力/工具/流程）+ pytest 全量 0 新 fail

## 边界
### 做
- ① `_extract_triples`（document_profile_learner.py）规格识别扩展：拆散 M 螺柱（"螺柱 M5 8"）+ GB/T 标准号作 subject
- ② `build_from_triples`（knowledge_graph.py）节点类型按 subject 判
- ③ `_search_knowledge_graph`（hierarchical_context.py）匹配改进（让 KG 节点被 G25a 工序名查到）
### 不做
- **不上向量**（exp-g25a-cohesive-model：精确术语场景 KG+分层为主，向量似是而非）
- 不重写 `_extract_triples` / `build_from_triples`（加规则，最小改）
- 不碰 DB knowledge_search（它工作，是 aux 现有来源）
- 不改前端

## 模糊点（进 PlanMode 前清零）
1. **范围**：✅ 三件配套（B 要 ①抽规格-工序 + ②节点类型 + ③按工序查关联规格）
2. **③ 方向**：✅ **B 结构改**（规格-工序关联）。A 补丁否决（query=G25a 工序名不含规格 M4，label/keyword 补丁治标有限）。B 三处改：triples 抽规格带 current_section + build_from_triples 建规格-工序边 + _search_knowledge_graph 按工序名查关联规格。
3. **② 节点类型判定规则**：M\d+ / GB-T → spec？螺柱/螺栓/螺母 → material？工装代号 T2D → tool？（设计细节，PlanMode 定）
4. **① 规格识别边界**：M\d+×\d+（M5×8）/ GB/T\d+ / 工装代号（T2D...）/ 螺纹销？全 or 子集？（PlanMode 定）

## 下游
- → PLAN（同 slug `craft-kg-quality`）

## 纠错（2026-07-26 v1→v2，N5 端到端发现）
**v1 的 N2 靠 `_section_at` 取章节标题作 process，实测失败**：
- 装配文件 `3.1/3.2` 是工艺规程条款（非工序标题），`_collect_headers` 在去 tag content 抽 0 headers → process 全空 → proc→spec 边 0 个
- 进一步发现：G25a 表格「工序名称」列填的是**工种（钳/机）**，**不是真工序名**
- 真工序名在两处：**G19a 工艺流程图**（`extract_process_steps` 的 skeleton）+ substep.content 的 `1.1 装配前的产品完整性检查` 编号开头
- `extract_assembly_steps`（生成时用）已处理 colspan（按 header 列名读列），产出 `asm[step_no]={name(工种), substeps:[{content,material,instruments}]}`

**v2 方向**：废弃 N2 的 `_section_at` 路径（_collect_headers 保留给 Pattern 3/5 兜底），改 **N2'：learn 接 `extract_assembly_steps`**，按 G25a 表格行解析，`process = skeleton[step_no-1]`（G19a 真工序名，**不用 asm.name 工种**），规格/参数从 substep.content 提。N1（spec_patterns）+ N3+N4（build NODE_SPEC + proc→spec 边 + 渲染）保留已 commit。
