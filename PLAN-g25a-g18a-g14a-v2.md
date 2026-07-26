# PLAN: G25a/G18a/G14a 生成质量修复 v2（回退 N2 + 新需求）

> slug: `g25a-g18a-g14a-v2` | ALIGN: `ALIGN-g25a-g18a-g14a-v2.md`（截图标注） | seal 后不可变

## Context（为什么改 + v1 纠错）
2026-07-26 晚用户重新审验，下午 N2+N3 方向做反：
- N2（工序名称列改真工序名 skel[k-1]）错 → 用户要工种钳/机/检验留工序名称列，真工序名放**工序内容**开头
- N3（G18a source 填"待补"）错 → 用户要 source = 物料用于哪个工序（craft_kg 物料→工序下层）
4 改动一次性落实 + 南天门升级（ALIGN 截图标注）。

## 改动清单

| 文件 | 改什么 |
|---|---|
| `writing_agent.py` | **1a** :850-853 `step_name` 回退 `[asm.get(k,{}).get("name","钳") for k in sorted(asm)]`（工种，撤下午 N2）。**1b** :1665-1671 `_generate_g25a_per_row_parallel` content prompt：把"不要带钳/机前缀"改为"每工步开头写工序名 `{name}`"（name=skel[i-1] :1629 已取）。**2b** G18a source 从 craft_kg 查（回退 :1357-1358 排除）。**4a** :1338-1346 G14a derive upstream 注入 G25a aux_materials 全文 |
| `document_profile_learner.py` | **2a** `_extract_triples_from_substeps` :280-290 对有 `sub["material"]` 的 substep 加 `{s:process(skeleton[i]), r:"使用", o:material, process:process}` triple → build_from_triples :256-262 自动建 proc→material REQUIRES 边 |
| `orchestrator.py` | G18a 分支 :988：**2b** source = craft_kg `get_neighbors(mat_id,"requires",direction="in")` 取工序名；**3** remarks = 主物料/关键配件（非标准件/耗材）+ craft_kg 命中写工序。G14a 分支：**4b** comp_code/comp_name 填 G1a field_values（component_code/component_name） |
| `tests/` | 单测追加 |

## 主要配件判定（G18a remarks，用户拍）
标准件（螺钉/螺栓/螺母/垫圈/销 + GB-T/QJB/HB）+ 耗材（布/乙醇/胶/润滑脂/漆/油）→ 备注空；其他（主物料+关键配件）+ craft_kg 命中 → 写工序名；没命中 → 空。

## 禁区
- 不臆造（备注 graph 没命中留空 / G14a provenance 不放宽靠上游注入全辅料）
- 不改 craft_kg build（物料 triple 走现成"使用"branch）/ 不改 N1（extract 跨页保留）

## 节点顺序（每节点 1 commit）
N1（改动1 G25a 回退工种 + content 工序名打头）→ N2（改动2 物料triple + G18a source graph）→ N3（改动3 G18a 备注）→ N4（改动4 G14a 写齐）→ N5（端到端 playwright）。

## 验证
- 单测：step_name=工种（回退）+ 物料 triple 产 + G18a source/remarks graph + G14a derive 全辅材
- 全量 pytest 0 新 fail（基线 717）
- 端到端（playwright project=4 + 云端 qwen3）：G25a 工序名称列=钳/机/检验 + 工序内容"装前准备：1.1..."；G18a source=物料用于工序 + 备注=主物料/关键配件写工序；G14a 封面+辅材定额全

## 风险
- 物料 triple 物料名清洗（sub.material 含规格/牌号混）
- 标准件/耗材词表覆盖（漏判误写）
- G14a G25a aux_materials 注入要全（不全 derive 还是少）
- G14a 封面 G1a field_values 需 G1a 在 G14a 前生成（phase 顺序）

## 复用
- `name=skel[i-1]`（:1629）→ content 工序名前缀
- craft_kg 单例 + `get_neighbors(mat_id,"requires",direction="in")`（knowledge_graph.py:95）→ material→proc 查询
- build_from_triples :256-262 `r=="使用"` branch → 物料 triple 自动建边
- G1a field_values component_code/component_name → G14a 封面
- G25a aux_overrides/filled_data.aux_materials → G14a derive 全辅材源
