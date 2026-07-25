# 需求对齐卡:triples 抽取增强 · 规格-参数关联

## 背景（为什么做）
craft_kg graph 架构能表达"规格-参数关联"（M5螺栓 —力矩— 3.6N·m），但 `_extract_triples`（document_profile_learner.py:117-190）当前力矩 pattern 的 subject 是 `[一-鿿]{0,6}`（中文 0-6 字）或 `current_section`（工序/泛词），**不含规格**（M5/螺栓/螺钉）。所以抽到「装配→力矩3.6」而非「M5螺栓→力矩3.6」。graph 缺规格-参数关联，query「M5/螺栓」查不到对应力矩。

工艺文件表述（G25a sample 实证）：`用 GB/T68-2000 的 M5×8 螺栓...拧紧...力矩为 3.6±0.4 N·m` —— **规格+力矩同句**，规则可抽。

## 目标
增强 `_extract_triples`，抽「规格（螺钉/螺栓/工装代号）→ 参数（力矩等）」关联，塞进现有 graph（架构不变）。

### 成功标准（可观察）
- learn 后 craft_kg 有「M5螺栓」节点 + 「—力矩— 3.6N·m」边。
- `_search_knowledge_graph("M5")` 或 `"螺栓"` → 查到力矩（N3 能用）。
- 不回归：现有 triples（温度/压力/标准/工具/流程）抽取不破。

## 边界

### 做
- `_extract_triples` 加规格 pattern（M\d+ 螺栓/螺钉 / GB/T / 工装代号 T2D...）→ 参数关联。
- 单测（规格-参数抽对）。
- learn 验证（craft_kg 有规格-参数节点/边）。

### 不做
- 不动 graph 架构（networkx 已支持任意节点/边）。
- 不动前端。
- 不全量重写 `_extract_triples`（加规则，最小改）。

## 模糊点（进 PlanMode 定）
1. **规格 pattern 范围**：M\d+ 螺栓/螺钉 / GB/T 标准 / 工装代号（T2D...）/ 螺纹销？全 or 子集？
2. **关联范围**：只力矩 or 所有参数（温度/压力/时间/...）？推荐先力矩（用户场景：M几螺钉→力矩）+ 复用现有 qty_patterns 扩。
3. **subject 取值**：规格全称「M5×8 螺栓」or 简化「M5 螺栓」？

## 下游
- → PLAN（同 slug `triples-spec-param`）
