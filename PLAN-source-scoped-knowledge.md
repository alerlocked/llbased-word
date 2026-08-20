# PLAN: 知识按来源隔离——勾选升级为项目工作区域 + 图谱来源分开录

> slug: `source-scoped-knowledge`（对齐卡 `ALIGN-source-scoped-knowledge.md`，方向已用户拍板 2026-08-20）

## Context

多型号/多专业工艺文件大量进来时，知识查询会跨来源串数据（G18a 代号查名称静默填错型号、KG 参数后学顶掉先学）。用户拍板解法：不建型号维度（素材无明确型号，靠猜不可靠），**来源（素材文件）作一等维度**——项目勾选的素材 = 工作区域，所有知识查询只认这个范围。

核心设计（已核实代码定案）：
- **工作区域正源 = `CreationProject.material_ids`**（models/database.py:89，添加素材时已写入）。生成请求已带 project_id → 后端自读，前端不传 ids。**material_ids 为空 = 不过滤（全量，兼容现状）**。
- **KG 节点 id 加来源前缀** `{doc_id}::{safe_id}` 实现分开录：跨来源天然不合并、同来源重学幂等（merge_from 现有逻辑）、label 不带前缀（seed 匹配不受影响，已验证）。存量 craft_kg 清空重学（用户已同意，现文件仅 1.8KB，全部来自 documents/1）。
- 存量数据已验证：material_catalog 62 行 / process_steps 12 行全部带来源 '1'，无 NULL 风险。

## 改动清单（5 节点）

### N1 · 检索基础设施（架构层）
| 文件 | 改什么 |
|------|--------|
| `backend/app/services/hierarchical_context.py` | ① 新私有方法 `_resolve_source_filters(project_id) -> Optional[Dict]`：SessionLocal 查 CreationProject.material_ids，空/无 → None，非空 → `{"source_ids": [str(i)...]}`（按请求缓存）；② `build_context`（:649）L2/L3 下传 filters（`search_tables(query, top_k=3, filters=f)` :716、`global_keyword_search(query, top_k=10, filters=f)` :745）；③ `_get_all_documents`（:212）filters 分支加 `Material.id.in_(source_ids)`；④ **修缓存污染 bug**：末尾 `self._documents_cache = documents` 改为仅 `filters is None` 时写（否则 filtered 调用污染全量 TTL 缓存） |
| `backend/app/services/knowledge_search.py` | `search_materials` / `find_material_by_code` 加 `source_ids: Optional[List[str]]` 参数 → `MaterialCatalog.source_doc.in_(source_ids)`；`build_knowledge_context_text` 透传 |

### N2 · 录入侧来源落地（架构层）
| 文件 | 改什么 |
|------|--------|
| `backend/app/services/knowledge_graph.py` | `build_from_triples(triples, source=None)`：source 非空时**所有** add_node/add_edge 的 id 加前缀 `f"{source}::"`（含 param_id、"禁止"分支 sid；不改 add_node 本身——其它调用方存在） |
| `backend/app/api/profile.py` | `_feed_craft_kg(triples, doc_id)` 签名加来源 → `build_from_triples(triples, source=str(doc_id))`；3 个调用点穿 doc_id（learn :260 / learn-file :330（doc_id 现成）/ learn-batch :426（按 file_ids 逐文件建再 merge）） |
| `backend/app/services/knowledge_extractor.py` | `extract_and_save`（:345）去重 existing set 从**全表**载入改为 `filter(MaterialCatalog.source_doc == doc_id)`（同来源内去重，跨来源各自录；顺带修全表载入性能尾巴） |

### N3 · 生成链路穿透（架构层）
| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/orchestrator.py` | ① 新方法 `_project_source_ids() -> Optional[List[str]]`：读 `self._collected_info["context"]["project_id"]`（已核实可达，:489→:670-709→:493 变量链）→ 查 CreationProject.material_ids，按请求缓存；② `_enrich_names_from_catalog`（:1024）G18a 传 source_ids 给 find_material_by_code；③ `_inject_g25a_aux_context`（模块级 :57，调用点 :2843）签名加 `source_ids`，传给 extract_reference_methods 和 _search_knowledge_graph |
| `backend/app/services/hierarchical_context.py` | `_search_knowledge_graph`（:1017）加 source_ids：seed 循环内 `nid.split("::",1)[0] not in source_ids → skip`（无 `::` 旧节点过滤时全跳，配合清空重学）；`extract_reference_methods`（:955）filters 透传（内部 global_keyword_search 一行） |
| `backend/app/api/agent.py` | `_build_orchestrator_context` 的 `_multi_pass_retrieval`（:1603）/ `search_meta_info` / `get_material_status`（:1472-1481）传 filters（否则 L0 元信息/多轮检索绕过工作区域） |

### N4 · 工作区域 API + 前端（项目层）
| 文件 | 改什么 |
|------|--------|
| `backend/app/api/creation.py` | ① GET /materials（:270）items 补 `folder_id`/`model`/`specialty`；② 新端点 `DELETE /projects/{id}/materials/{mid}`：从 project.material_ids 移除引用（不动素材本体——区别于删项目级联删 :210）；③ 项目素材已选标记（GET /projects/{id}/materials 或项目详情带 material_ids） |
| `frontend/src/components/workspace/MaterialDrawer.tsx` | Inline 列表 = 工作区域 UI：每项"已选/未选"徽标 + 勾选切换（勾=加 material_ids，取消=移除）；文件夹树整组勾/取消（复用 handleLearnFolder 的 folder→fileIds 逻辑 :451） |
| `frontend/src/components/common/AddMaterialDialog.tsx` | 素材表按文件夹分组 + 整组勾选（selectedRowKeys 机制保留） |

### N5 · 存量治理 + 收尾
| 文件 | 改什么 |
|------|--------|
| `backend/data/knowledge_graph.json` | 清空重学：删文件 → learn documents/1 → 验证节点全带 `1::` 前缀、检索过滤生效（真实链路冒烟） |
| `backend/data/craftdoc.db`、`backend/data/database.db` | 删两个 0 字节空壳（已 grep 确认零引用，真库 data/database/craftdoc.db） |
| `ARCHITECTURE.md` | §4 检索 + §5 数据存储补"来源工作区域"机制（lead 收尾规范） |

## 禁区

- **不碰生成主链语义**：draft_complete 准入守卫 / gated / review_pipeline / intent 路由（review-pipeline 成果，零改动）
- **不碰 `reference_materials` 内容注入机制**（prompt 参考与知识过滤正交，保留现状）
- **MaterialsPanel（AICreation）死组件不动不复活**；ConversationPanel 独立系统不碰
- **StandardClause/Standard 标准条款豁免来源过滤**（公共参考数据，无 source 字段——记录在案的显式豁免，不为此加列）
- 型号维度列 / specialty NULL 回填 / KG 可视化 / 认证多用户隔离——ALIGN"不做"清单
- 单测只加来源相关（幂等/过滤/前缀），不铺覆盖率

## 验证

- 每节点：`cd backend && pytest tests -k "<节点关键词>" -x`（N1: hierarchical+keyword+knowledge_search / N2: knowledge_graph+profile+extractor / N3: orchestrator+g25a+enrich / N4: creation）
- N2 单测必含：两来源同规格不同参数值 → 两节点共存互不覆盖；同来源重学 → 幂等不重复
- N4 前端：`cd frontend && npx tsc --noEmit`
- N5 真实链路冒烟：learn documents/1 → KG 节点 `1::` 前缀 → 默认项目（material_ids=[1]）生成检索只回源 1；产物进 `.test-runs/source-scoped-knowledge/`
- 全量回归：`pytest tests`（基线 918 passed 0 failed 不回归）
- ⚠ N1-N3 触及 CONTRIBUTING 架构层隔离清单（hierarchical_context / knowledge_graph / agent.py 主链 / orchestrator）→ 走独立 feature 分支 + PR + /pr-review（照 PR #64 惯例），不直推 main

## 经验引用（Writer/Reviewer 必读）

- `exp-craft-kg-feed-from-learn`：数据层三问——save 调用点必查、`count>0` 守卫静默跳过陷阱
- `exp-retrieval-cleanup-and-dimensions`：维度穿透 filter 模式（本任务沿同一模式扩 source_ids）
- `exp-g25a-cohesive-model`：craft_kg 是活组件，勿与老死壳混淆
