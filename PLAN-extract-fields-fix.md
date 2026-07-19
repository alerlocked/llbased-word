# PLAN: G12a/G14a 双层列头 extract 全面支持（v2）

> re-seal 2026-07-19。slug=`extract-fields-fix`。v1（序号过滤 `25d4876`）回归已 revert（`1e3e723`），重传 source 诊断 5 根因后改 v2。对齐卡 `ALIGN-extract-fields-fix.md`。

## 改动清单（6 改，commit 分层）

| 改 | 文件:行 | 内容 |
|---|---------|------|
| A | `table_schemas.py:25` | `FIELD_ALIASES["material"]` 加 `"材料"` |
| B | `structured_extractor.py:360` | label/cell 去空格匹配（`re.sub(r"\s","",...)`） |
| **B+** | `:357-364` | **label 长度降序匹配**（长先占列，修短别名 `名称` 抢 `材料名称...`） |
| C | `:366-377` | **best_col_map 双层合并**：best_header_idx+1 若 ≥2 label（下层列头）→ 合并补缺（不覆盖上层）+ `data_start=best_header_idx+2` |
| D | `:379-388` | 数据行残留过滤（cell 与双层列头 label 重叠 ≥2 且 ≥半数 → 跳，**不靠序号数字**） |
| D+ | `:17-46` `_NOISE_PATTERNS` | 加 `^(更改标记|更改单号)\s*$` |

**commit 分层**：commit1 A+B+B+（material_desc 主修，0 风险）/ commit2 C（quota 列纠正）/ commit3 D+D+（兜底）。每步全量 pytest + 真实生成验证。

## 禁区
- G5a 不修（file_references 覆盖）
- G12a unit（根因 4 列轴错位，上游 `_expand_table_grid`）留可选增强，不进首版
- 不改生成 prompt / derive / 前端 / 模板 / `_expand_table_grid`

## 验证
1. 真实 fixture（禁简化）：从 content.html table5/6 `_table_to_markdown` 抠 G12a/G14a markdown → `tests/fixtures/material_tables.py`
2. `pytest tests/test_structured_extractor.py -v`（新 TestDualHeaderMaterialTables：净重/单套 不串入、material_desc 抽真材料、part_name 不误收、seq 不含更改标记）
3. 全量 pytest 不回归（G18a 同双层受益）
4. 真实生成 G12a/G14a/G18a：G12a quota 无"净重"、material_desc=材料名；G14a material_desc=['白棉布...']、unit=['m']
5. G5a 未受影响
