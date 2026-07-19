# PLAN: G12a/G14a extract 双层列头修复

> seal 2026-07-19。slug=`extract-fields-fix`。对齐卡 `ALIGN-extract-fields-fix.md`。
> 分支 `main`（与 gen-test-fixes 一致）。

## 改动清单（G12a/G14a 同批改，不逐章 stop-and-test）

| 文件 | 改什么 |
|------|--------|
| `backend/app/services/structured_extractor.py` `_extract_tabular_fields`（:330-390） | 增强**数据行识别**：`data_start` 后跳过"双层列头细分行"（序号列空/非数字），只取真数据行（序号列匹配 `^[1-9]\d{0,2}$`）。复用 G5a `extract_file_references`（hierarchical_context.py:1509）的序号判据。读源码定具体：`best_col_map` 定位序号 key → 数据行过滤加序号校验 → 双层列头细分行（无序号）自动跳过 |
| `backend/tests/test_structured_extractor.py` | 加 G12a/G14a 双层列头 extract 单测（fixtures 用 documents/1 table6/7 源 markdown），断言 `quota`/`material_desc` 抽全；保留现有 G18a 等用例不破 |

## 禁区
- 不改 G5a（file_references 覆盖已 OK，仅 TODO 标注）
- 不改 `_table_to_markdown` colspan（§1.10 commit `5b97f8d` 已修；G12a/G14a 主因是双层列头**列映射**非 colspan）
- 不改生成 prompt / writing_agent 生成逻辑 / derive / 前端
- 不碰南天门核心区

## 验证
1. `cd backend && conda run -n gywj python -m pytest tests/test_structured_extractor.py -v`（新单测过）
2. 全量 pytest 不回归（`_extract_tabular_fields` 通用，验 G18a/G10a 等不破）
3. 改完彻底重启后端（gywj）+ 真实生成 documents/1：G12a `quota` / G14a `material_desc` 的 `fields_found` 对齐源行数；G5a 仍 OK
4. **一次性 web 验收**（用户定）：G5a/G12a/G14a 生成结果一起看，不逐章 stop-and-test
