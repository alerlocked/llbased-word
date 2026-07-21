# PLAN: ARCHITECTURE.md(单一架构源 + 维护机制)+ P1-1 catalog 索引

> slug: `arch-catalog-index` · 项目: localknowledgebase-word(主)→ win10
> 对齐卡: `ALIGN-arch-persist-index.md`(P1-2 已弃,现象没了)· seal 后不可变

## Context(为什么改)
两个问题:
1. **架构无单一源**——散在 `CLAUDE.md:35-93`(旧)+ 代码,易腐。用户要固定一个文件(ARCHITECTURE.md),别处不重复,且每次架构变更要驱动更新。
2. **P1-1 catalog ~1s 阻塞**——`material_catalog.standard_code` 无索引,G18a enrich 33 次 exact 查全表扫。加索引(结构化方向,非向量,不重蹈 2026-06-14 废弃的向量层)。

P1-2(刷新丢)弃——用户确认现象已没。

## 改动清单

### 节点 1 · 新建 ARCHITECTURE.md(当前真实架构)— 1 commit
新建 `ARCHITECTURE.md`(项目根),内容**对照代码真实状态**(Explore 实证):
- **header**:单一架构源 + 维护规则("架构变更时更新,见 CLAUDE.md 规范")
- **Agent 系统**:功能 Agent = `writing`/`review`/`proofread`(registry 注册);Tool = `compliance_checker`/`terminology_mapper`;workflows(full_edit/quick_edit/review_only/proofread_only);orchestrator 状态机(idle→intent→...→completion + draft_analysis/paused/error)。**Search Agent 已删,Compliance 是 review 的 tool 不是独立 Agent**。
- **生成流程**:`POST /agent/generate-stream` → `orchestrator.process_intent` → SSE(mode/progress/content/result/error);**source-driven 直注**(extract_*:assembly_steps/process_steps/process_card_steps/file_references/doc_catalog/assembly_overview → orchestrator 注入 task params → writing_agent 直填)= 真主路径。
- **上下文 + 检索**:HierarchicalContext 4 层(L0 meta/L1 table/L2 table html/L3 keyword)+ material filter(型号/专业穿透);**3 活路径**(source-driven 直注[主]/ HierarchicalContext[兜底]/ material_catalog 结构化[G18a enrich]);**废弃组件**(向量/图谱/UnifiedRetrieval/SearchAgent,2026-07-05 cleanup 删)。
- **数据存储**:`documents/{material_id}/`(index/content.html/content.json/vlm)+ DB 表(MaterialCatalog/ProcessStep/Standard/StandardClause/StepMaterial/StepTool/Material)+ profiles/ + tasks/ + memory/。
- **前端**:React + Zustand(creationStore persist localStorage)+ Tiptap;AIChatPanel → generate-stream SSE → ProcessTableEditor(表格)/ProcessContentView(卡片)/Tiptap。

### 节点 2 · CLAUDE.md 架构段 → 指针 + 维护规范 — 1 commit
`CLAUDE.md`(项目):
- 架构段(35-93)替换为指针:"架构见 `ARCHITECTURE.md`(单一源)"。保留技术栈表(栈不变)。
- 加**架构维护规范**:"涉及架构改动(agents/检索/数据/生成流程),lead 收尾必须更新 `ARCHITECTURE.md`;DEV-LOG 当前状态记架构变更点。"

### 节点 3 · P1-1 standard_code 索引 — 1 commit
| 文件 | 改什么 |
|------|--------|
| `backend/app/models/database.py:385` | `MaterialCatalog.standard_code` 加 `index=True` |
| `backend/app/database.py` `init_db()`(或 `init_db.py`) | 加 idempotent `CREATE INDEX IF NOT EXISTS idx_material_catalog_standard_code ON material_catalog(standard_code)`(已有表建索引,不重建,不影响数据) |

> 无迁移机制,用 `IF NOT EXISTS` idempotent。`find_material_by_code`(knowledge_search.py:55)exact,G18a `_enrich_names_from_catalog`(orchestrator.py:1014)33 次 first → 索引查。

### 节点 4 · sync win10 — 1 commit
cp `ARCHITECTURE.md` + `CLAUDE.md` + `database.py` + `init_db`(若有)主→win10。

## 禁区
- ❌ 向量/图谱(已删,不复活)
- ❌ source-driven(A)/HierarchicalContext(B)检索路径(不动)
- ❌ G18a enrich 逻辑(只加索引加速)
- ❌ 重建 material_catalog(只 CREATE INDEX)
- ❌ P1-2 持久化(弃)
- ❌ 自动 hook 驱动架构更新(hook 保护区,人/lead 规范驱动)

## 验证(端到端)
1. **ARCHITECTURE.md**:内容对照代码真实(3 活路径/功能 Agent/状态机/数据表),无过时(向量/图谱标已删)
2. **P1-1**:`CREATE INDEX IF NOT EXISTS` idempotent 不报错;`material_catalog` 数据不变;G18a enrich 索引查;pytest 676 回归
3. **CLAUDE.md**:架构段指针 + 维护规范在
4. **sync**:win10 一致

## 执行注意
- ARCHITECTURE.md 写**真实状态**(Explore 实证),不照搬 CLAUDE.md 旧描述
- P1-1 idempotent,确认 init_db 调用点(启动跑)
- 维护机制人/lead 驱动(CLAUDE.md 规范 + DEV-LOG 记变更)
