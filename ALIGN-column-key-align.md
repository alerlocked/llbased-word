# 需求对齐卡:G10a/G14a/G12a 前后端 column-key 对齐

> slug: `column-key-align` · 项目: localknowledgebase-word · 2026-07-21

## 背景
guard(`scripts/hooks/guard-column-align.py:28` KNOWN_DIFFS)白名单的 3 个表前后端 column-key 不一致,前端按自己 key 取值取不到后端数据 → 潜在空列/错位。TODO P0 ②。

## 根因(已查清)
同一列,backend template key ≠ frontend layout key:
| 表 | backend key | frontend key |
|---|---|---|
| G10a 专用装备明细 | `for_component_code` / `for_component_name` | `for_code` / `for_name` |
| G14a 辅助材料定额 | `component_code` / `component_name` | `comp_code` / `comp_name` |
| G12a 主要材料定额 | (无) | 多 `blank_yield`(可制件数) |

前端 `ProcessTableEditor` 动态 `row[col.key]`(col.key 来自 layout)→ 按前端 key 取,后端 filled_data 用 backend key → **取不到 → 空列**。guard 发现了但塞 KNOWN_DIFFS 白名单跳过,没报错,隐患在。

## 改动面(Explore)
- **后端 backend key 用点**:`assembly_process_template.json`(G10a/G14a 定义)+ `structured_extractor.py:71-72` `_CODE_LIKE_KEYS`(代码类 key 集合)。G14a 的 `component_code/name` 还在 **G4a**(writing_agent:912/913,hierarchical_context:1645/1646)用——**改 G14a 不能碰 G4a**。
- **前端 frontend key 用点**:`layouts/G10a.ts`/`G14a.ts`/`G12a.ts` dataColumns 定义。`ProcessTableEditor` 动态取(layout 改即生效)。
- **已有数据**:用 backend key。改 key 后旧数据该列前端取不到。

## 方案

### 方案 A · 后端改(推荐)
backend template key → frontend key 名,前端不动:
- template:G10a `for_component_code/name`→`for_code/name`;G14a `component_code/name`→`comp_code/name`;G12a 加 `blank_yield`
- `_CODE_LIKE_KEYS`:加 `comp_code`/`for_code`,**保留 `component_code`**(G4a 用)
- 改 4 处(template 3 + 常量 1),前端 0 改
- 保留 `blank_yield` 功能(可制件数,材料定额有用)
- ⚠️ 确认 G4a 不受影响(G4a template `component_code` 不动,代码硬编码 `component_code` 不动)

### 方案 B · 前端改
frontend layout key → backend key 名,后端不动:
- layout:G10a `for_code/name`→`for_component_code/name`;G14a `comp_code/name`→`component_code/name`;G12a 删 `blank_yield`
- 改 3 处 layout,后端 0 改
- **丢失 `blank_yield` 功能**

## 目标 / 成功标准
- G10a/G14a/G12a 前后端 column-key 一致 → 前端取到值,无空列
- guard `KNOWN_DIFFS` 这 3 个表清空(对齐后删白名单)→ guard 0 告警
- 可观察:生成 G10a/G14a/G12a,前端表格该列有值(代号/名称/可制件数)

## 边界
**做**:G10a/G14a/G12a key 统一 + guard 白名单清
**不做**:其他表 / G4a(不碰)/ 非 column-key 问题

## 模糊点(待对齐)
1. **方向**:方案 A 后端改(推荐)vs 方案 B 前端改
2. **已有数据**:迁移旧 key / 重新生成 / 不理(测试数据)
3. **G4a 隔离**:方案 A 执行时确认 G4a component_code 不受影响(PLAN 验证)

## 下游
→ PlanMode 定精确改点 + G4a 隔离验证
