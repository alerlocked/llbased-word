# PLAN: 倒推强节点（工艺链路配套关系补齐）

> slug: `derive-strong-node` · 关联 `ALIGN-derive-strong-node.md`
> 用户决策：架构=**替换**（移除 Phase 3 内倒推，归强节点）/ 待补=字符串 `"待补"` / 溯源失败=丢弃 / 验收=行数对比+人工抽样
> seal 后不可变。Reviewer 从 git 读本文件。

## Context

工艺文件项目「G19a 流程图 → G25a 工艺内容 → 前置配套关系（G18a 零件 BOM、G10a 工装、B12a 工具量具、G14a 辅材、G5a 引用文件）」倒推链路当前是**弱兜底**：`_derive_list_from_upstream` 只在「structured 抽空 + LLM 空 + upstream 有」（三空）时触发（`writing_agent.py:1167-1172`），原文抽出残缺数据就跳过 → 明细表只拿到原文有的部分，配套关系补不齐。

升级为**强节点**：移除 Phase 3 内弱兜底，倒推逻辑统一提到 orchestrator（`generated_chapters` 就绪后、Review-Retry 前）无条件跑，覆盖所有明细表，加**字段边界声明 + 溯源校验 + 原文优先合并 + 推不了标「待补」**四道约束防臆造。

前提已实证（调研）：G19a 在 Phase 1 单独生成、Phase 2+ 只读不改，倒推依赖稳定；`_derive_list_from_upstream` 输入 `{code:{title,text}}` 与 orchestrator 的 `generated_chapters` 同构（`orchestrator.py:2787-2790`）；orchestrator 通过 `self._agents["writing"]` 拿 writing 实例。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `orchestrator.py`（插入点：`generated_chapters` 构建后、`# Review-Retry` 注释 2796 行前） | 新增**倒推强节点**：遍历 `results`/`task_keys` 找明细表 chapter（G4a/G5a/G10a/G12a/G14a/B12a/G18a），调 `self._agents["writing"]._derive_list_from_upstream(chapter_code, chapter_type, chapter_title, slot_cols, ai_guidance, upstream=generated_chapters)` 无条件倒推。结果经三步处理（溯源过滤 → 待补标注 → 原文优先合并）后按 `table_type` 分流写回 `results[idx]`（single_row_list→`filled_data` / dual_list→`left_data`+`right_data`） |
| `writing_agent.py:1161-1203`（Step 3b Derivation fallback） | **移除**这段 Phase 3 内倒推兜底调用（替换，归强节点）。`_derive_list_from_upstream` 方法（1327+）保留供强节点复用 |
| `writing_agent.py:_derive_list_from_upstream`（1327+） | **升级**(a)：返回前调**溯源校验**——倒推条目（如工装名/辅材牌号）必须能在 `upstream["G25a"]["text"]` 找到出处（关键词包含），否则丢弃该条目（宁可少不可假）。**(b)**：按 `chapter_code` 查字段边界表，推不了的字段值直接写 `"待补"`（不交 LLM 编） |
| 新增辅助逻辑（放 orchestrator 内私有方法） | `_provenance_filter(derived, g25a_text, chapter_type)`：丢弃 G25a 无出处条目；`_apply_missing_markers(derived, chapter_code)`：按字段边界表把推不了的字段值设为 `"待补"`；`_merge_derived_with_original(original_inner, derived, chapter_type)`：原文 structured 值优先，倒推只补原文缺的，同条目按 key 去重 |

## 字段边界声明（推不了 → "待补"）

来自调研倒推可行性矩阵，硬编码到 `_apply_missing_markers`：

| 章节 | 推不了的字段（值="待补"） |
|------|--------------------------|
| G12a 主材料 | 净重 / 材利用率 / 坯料尺寸 / 坯料件数 |
| G18a 配套 BOM | 零部组件代号（精准编码）/ 来自何处 / 每装配件数量（需批量）|
| G14a 辅材料 | 单套定额 / 本批定额（需批量信息）|
| G10a 工装 | 用于代号 / 使用单位 |
| B12a 工具量具 | 规格型号（靠工装台账）|
| G5a 引用文件 | 代号 / 页数 |
| 全部 | 工时类（time_setup/per_piece/total，靠工时定额标准，不从工艺方法推）|

## B12a / G18a 特殊处理

- **B12a（dual_list，脱孤儿）**：强节点显式覆盖（即便不在 `generation_phases` 也被倒推）；分栏倒推——工具 ← G25a `instruments` + content，量具 ← content 里量具词
- **G18a（零件 BOM，零件维度）**：从 G25a `content`/`references` 提**零件**（非工序维度），不强行对齐工序数；零件代号/来源推不了 → 标「待补」

## 禁区

- ❌ G19a / writing 模板填充主路径（G19a 隔离不动，`_do_template_fill` 主体不动）
- ❌ 前端（产出对齐现有 `filled_data`/`left_data`/`right_data` 结构，零改前端）
- ❌ 知识库 / 画像（方案 1，下一轮）
- ❌ 不重写 `_derive_list_from_upstream`（复用 + 加溯源/边界，不推倒）

## 验证

1. **行数对比**：`documents/1`（44 页装配规程）跑全链路，改动前后各明细表（G4a/G5a/G10a/B12a/G12a/G14a/G18a）行数——倒推合并后 ≥ 原文单 source
2. **人工抽样**：从倒推结果抽 5-10 条，核对在 G25a（`content`/`aux_materials`/`instruments`/`references`）有出处——验不臆造
3. **待补检查**：推不了的字段值 = `"待补"`，无 LLM 编造值
4. **pytest 回归**：`tests/`（writing_agent/orchestrator 相关）不引入新 fail

```bash
cd backend && /c/Users/alerl/.conda/envs/gywj/python.exe -m pytest tests/ -c pytest.ini --rootdir . --tb=short -q
# 全链路验收：触发 documents/1 生成（API 或诊断脚本），看各明细表 filled_data
```

## 拆分（执行 loop 节点）

1. **节点1**：升级 `_derive_list_from_upstream`（溯源校验 + 字段边界待补）—— 改 writing_agent.py，单测验证
2. **节点2**：orchestrator 插入倒推强节点 + 三个辅助函数（provenance/missing/merge）—— 改 orchestrator.py
3. **节点3**：移除 writing_agent.py:1161-1203 旧兜底（替换）—— 确认清单类在 Phase 3 内不再倒推
4. **节点4**：B12a/G18a 特殊处理验证 + documents/1 全链路验收（行数 + 抽样）
