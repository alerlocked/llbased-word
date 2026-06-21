# PLAN: G25a 检验收紧 + 全章节内容实证

> seal 后不可变。Reviewer 从 git 读本文件比对 diff。slug=content-quality。

## Context
contract-align 后用户反馈:G25a 检验项过多(30 检验 vs 10 工序)+ 各章节 AI 生成内容单薄。Explore 确认 **extract 源完整**(各章 500-33000 字符)→ 单薄是 **LLM 生成问题**,非源缺失。AI 结果未持久化,要重新生成实证。先 G25a 检验收紧 + 全章节实证,再据实证逐章(后续 lead)。

## 改动清单

### 节点B(先做,提供 baseline):全章节实证工具
| 文件 | 改什么 |
|------|--------|
| `backend/diagnose_all_chapters.py`(新建) | 扩展 diagnose_g25a 为全章节 loop。遍历模板 chapters,task 注入**严格对齐 orchestrator.py:2464-2528**:通用 `params.chapter_source_text=get_chapter_content(doc,title)`+`template_slots`+`chapter_code/type/title/ai_guidance`;G25a 额外 `assembly_steps`+`skeleton_steps`。逐章调 `_do_template_fill`,串行收集统计。复用 diagnose_g25a profile 加载 |
| 统计字段 | `rows_total`/`non_empty_rows`/`empty_cells`/`empty_rate`/`content_avg_chars`/`content_empty_rows`/`inspection_rows`(G25a)/`op_rows`,区分单薄成因(行少/字段空/content 短) |
| 输出 | 各章节质量表 + 按 empty_rate desc 排序给最单薄 2-3 章 + G25a baseline 检验数 + 各章源长度对照。清单类不传 upstream_chapters,标注 |

### 节点A:G25a 检验数量收紧(双保险)
| 文件 | 改什么 |
|------|--------|
| `writing_agent.py:1555-1557` step_msg | **去掉"简单工序 1 个"**(元凶)。改:仅关键质检工序(力矩/密封性/电气/位置度/关键尺寸,原文有检验要求)生成 1-2 检验点;普通装配动作(装密封圈/拧螺钉/搬运/清洗/涂胶)留空;总量 ≤ 工序数,宁缺毋滥 |
| `writing_agent.py:2026-2057` `_expand_inspection_rows` | 加**全局总量上限**:检验行 ≤ 操作行数,超量按 point 数 desc 优先保留多点工序。签名/调用点/检验行结构不变 |
| `diagnose_g25a.py` | 加 `inspection_rows`/`op_rows` 统计(before/after 量化 30→≤10) |

### 收尾
实证报告(单薄章节 + 根因=LLM 生成问题)落 wiki experience + memory;清临时。

## 禁区
- 不逐章大改(各章节修复 = 后续 lead)
- 不推翻 contract-align 检验机制(只调数量:step_msg + expand 上限,签名/调用点/结构/契约 guard 不变)
- 实证 task 注入必须对齐 orchestrator:2464-2528(失真则实证无效)
- 不碰 G22a

## 验证
- 节点B:`conda run -n gywj --no-capture-output python backend/diagnose_all_chapters.py` → 各章节质量表 + 单薄 2-3 章 + G25a baseline(30)
- 节点A:`conda run -n gywj --no-capture-output python backend/diagnose_g25a.py` → 检验行 ≤ 10;回归 `pytest backend/tests/test_structured_extractor.py`
- 先 B 后 A,量化 30→≤10

## ⚠️ 执行注意
- conda 环境 gywj(Python 3.10);改后端核心彻底重启(diagnose 直调 agent 无需重启 server)
- 实证串行跑真实 LLM(全章节几分钟),避免并发打满
- task 注入准确性 = 实证生命线
