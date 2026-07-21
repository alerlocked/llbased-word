# PLAN: G10a/G14a/G12a 前后端 column-key 对齐(方案 A 后端改)

> slug: `column-key-align` · 项目: localknowledgebase-word(主)→ win10
> 对齐卡: `ALIGN-column-key-align.md` · seal 后不可变

## Context(为什么改)

guard(`scripts/hooks/guard-column-align.py`)发现 G10a/G14a/G12a 三个表前后端 column-key 不一致(塞 `KNOWN_DIFFS` 白名单跳过):
- G10a:backend `for_component_code/name` ↔ frontend `for_code/name`
- G14a:backend `component_code/name` ↔ frontend `comp_code/name`
- G12a:frontend 多 `blank_yield`(backend 无)

前端 `ProcessTableEditor` 动态 `row[col.key]`(col.key 来自 layout)→ 按前端 key 取,后端 filled_data 用 backend key → **取不到 → 该列空**。隐患一直有(没报错因为白名单)。

**方案 A(用户定)**:后端 template key 对齐到前端名,前端 0 改。已有旧 key 数据**不理重生**。

> ⚠️ `component_code/name` 在 G1a(封面)、G4a(目录)、G14a(辅材)都用——只改 G14a,G1a/G4a 不碰。`_CODE_LIKE_KEYS` 保留 `component_code`(G1a/G4a 用)。

## 改动清单

### 节点 1 · 主项目对齐 — 1 commit

| 文件 | 改什么 |
|------|--------|
| `backend/app/templates/assembly_process_template.json` | ① G10a(行92-93):`for_component_code`→`for_code`,`for_component_name`→`for_name`。② G14a(行160-161):`component_code`→`comp_code`,`component_name`→`comp_name`。③ G12a(行143 `blank_count` 后)加 `{"key":"blank_yield","label":"可制件数","type":"number","fill_type":"structured"}`。 |
| `backend/app/services/structured_extractor.py` | `_CODE_LIKE_KEYS`(行70-73):`for_component_code`→`for_code` + 加 `comp_code`,**保留 `component_code`**(G1a/G4a 用)。结果:`{"part_code","equipment_code","component_code","ref_code","doc_number","for_code","comp_code"}` |

### 节点 2 · 验证(主项目)
- `pytest` 全量回归(基线 676 passed)0 新 fail
- 跑 `guard-column-align.py` 逻辑:G10a/G14a/G12a 0 mismatch(对齐后白名单留 harmless)
- G1a/G4a `component_code` 提取不回归(writing_agent:912 / hierarchical_context:1645 仍用 `component_code`)
- structured 提取冒烟:G10a/G14a/G12a 生成,该列(代号/名称/可制件数)有值

### 节点 3 · sync win10 — 1 commit
cp 主项目 `assembly_process_template.json` + `structured_extractor.py` → win10(镜像原则,业务代码同步)。前端 layout 不动(方案 A)。

## 禁区
- ❌ G1a / G4a 的 `component_code/name`(封面 + 目录,前端一致,不碰)
- ❌ 前端 layout(方案 A 后端改,前端 0 改)
- ❌ `scripts/hooks/guard-column-align.py` 的 `KNOWN_DIFFS`(南天门保护区,本项目 session 不碰;对齐后白名单留 harmless,要清走 NTM_MAINT)
- ❌ 数据迁移(用户定重生)
- ❌ 打包新 V0.2(本次只改 + sync,用户没要新包)

## 验证(端到端)
1. **对齐**:跑 guard 逻辑 → G10a/G14a/G12a 0 mismatch
2. **回归**:pytest 676 passed 0 新 fail;G1a/G4a component_code 提取正常
3. **取值**:生成 G10a/G14a/G12a,前端表格该列有值(代号/名称/可制件数)
4. **sync**:win10 backend import OK

## 执行注意
- template 是 JSON,改 key 名 + G12a 加一行,小心逗号/格式
- `_CODE_LIKE_KEYS` 是 set,改元素别破语法
- 改后彻底验证 G1a/G4a(都含 component_code)不回归
