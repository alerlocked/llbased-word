# PLAN: 阶段2 — G25a 相辅相成生成模型（KG + 分层上下文，不用向量）

> slug: `g25a-method-aux-bind`（seal 后不可变）
> ALIGN: `ALIGN-g25a-method-aux-bind.md` | 上游: 阶段1 `llm-reasoning-empty-fix`（done, fix 7a82a6c）
> 完整方案见 plan file；本文为执行版。

## Context

阶段1 止血（工艺方法不空）后，做用户真正要的**相辅相成**：辅料现状从上传文件 `substeps.material` 直填、工艺方法 LLM 现场编，**两者割裂**（工艺方法提到的辅料 ≠ 辅料列）；且工艺方法**没套用素材库现成工艺方法**。本阶段改成：套用素材（精准抽取同类工序工艺方法）+ 辅料标准（KG/in-context）+ LLM 同次产出工艺方法+辅料+参数 + 辅料覆盖辅料列（一致性绑定）。数据层 KG + 分层上下文，**不用向量**。

## 已定决策（2026-07-24）

- KG 持久化 = 文件 `data/knowledge_graph.json`（启动加载，复用 `knowledge_graph.py` networkx）
- 套用素材 = **增强精准抽取**（按工序名召回页面 → 抽工艺方法段落，非整页片段）
- 辅料参数 = **in-context 先行**（2a，检索标准文档+历史工艺 LLM 写参数标来源）；结构化下沉（2b）后续
- 工艺方法生成导向 = 套用素材 + 针对型号工件 + **用户输入需求导向（优先）**

## 改动清单（6 节点，每节点一 commit）

| 节点 | 文件 | 改什么 |
|---|---|---|
| N1 | `models/database.py`（MaterialCatalog）+ `services/knowledge_graph.py` + `main.py` | MaterialCatalog 加 `tech_params` JSON 字段（`[{param_name,value,unit,standard_source}]`）；全局 KG 文件 `data/knowledge_graph.json` 启动加载；KnowledgeGraph 全局单例（从 Profile.graph 解耦为全局工艺 KG） |
| N2 | `services/hierarchical_context.py` | 新增套用素材精准抽取方法：`global_keyword_search` 按工序名召回页面 → 从页面抽**该工序的工艺方法段落**（工序级，非整页片段） |
| N3 | `services/hierarchical_context.py` | L3.5 KG 层：`_search_knowledge_graph(query,max_tokens)`（实体提取→KG 查辅料-参数 + StandardClause）+ `build_context:726` 接入 + L3 让 30% token 给 KG |
| N4 | `agents/orchestrator/orchestrator.py`（`:2711-2728` g25a 注入段） | G25a 注入扩展：除 assembly_steps/skeleton_steps/overview，加 `reference_methods`（N2 套用素材）+ `aux_standards`（N3 KG 辅料标准） |
| N5 | `agents/functional/writing_agent.py`（`gen_one :1597-1614`） | step_msg 加"套用素材参考"+"辅料标准"+"用户需求导向"段；输出改同次产出 `[{row,slot:content/aux_materials/params,value}]`；后处理 LLM 产出辅料覆盖 `structured_values` 辅料列（substeps 直填退为 fallback） |
| N6 | 验证 | pytest 回归 + G25a 冒烟（套用素材可溯源 + 辅料参数有来源 + 辅料列与工艺方法一致） |

## 禁区

- 不上向量库。
- 不动阶段1 的 `llm_service.py`。
- 不动其他 source-driven 章节（G4a/G5a/G18a/G12a/G14a/G22a extract 直填保持）。
- 不一次性人工录大辅料参数库；不用 StandardClause 装具体参数。
- 本轮只主仓；win10/麒麟同步后续。

## 验证

1. 冒烟：G25a 补齐 → 工艺方法非空且可溯源套用素材；辅料列 = 工艺方法提到的辅料；参数有标准来源。
2. L3.5 KG 层不挤占 L4；KG 空/有数据两态不崩。
3. pytest 676 passed 0 新 failed；阶段1 不回归。
4. 内网 qwen3 部署验证（用户，和阶段1 一起测）。
