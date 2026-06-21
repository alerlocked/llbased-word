# PLAN: G25a 检验工序行 + 前后端契约校验 + docx2pdf 修复

> seal 后不可变。Reviewer 从 git 读取本文件比对 diff。slug=contract-align。

## Context

工艺文件项目两个缺口:① G25a 装配卡后端生成 inspection(检验)但前端无对应列→丢弃;真实工艺文件里检验是**单独成行的工序**(工序名=「检验」)。② docx2pdf 三方法全挂。目标:检验按真实格式显示(检验行)+ 契约校验防"只改一边"+ 修通 docx2pdf 固化。不含生成质量优化(后续单独)。

## 改动清单

### 节点A:G25a 检验工序行(方案Y:merge 后处理,不动 g25a-perstep 并行核心)

| 文件 | 改什么 |
|------|--------|
| `backend/app/agents/functional/writing_agent.py:1521` | slot_keys 增补:`if chapter_code=="G25a" and "inspection" not in slot_keys: slot_keys.append("inspection")`(模板删列后 1571 `if s in slot_keys` 会丢 LLM 的 inspection slot,必须补回) |
| `writing_agent.py:1536-1546` | step_msg 末尾加 inspection 写法指引:列关键检验点,每点 `\n` 独占一行;简单工序1点/复杂多点;无则留空 |
| `writing_agent.py`(模块级 helper) | 新增 `_expand_inspection_rows(merged_rows)`:每行 inspection 值按 `[\n\r]+` 拆点,每点→检验行 `{step_name:"检验",content:<点>,其余9列key:""}`,从操作行移除 inspection |
| `writing_agent.py:1216` 后 | 插入 `if chapter_code=="G25a" and merged_rows: merged_rows=_expand_inspection_rows(merged_rows)` |
| `backend/app/templates/assembly_process_template.json:249-250` | 删 G25a inspection 列(下游全按 columns 动态渲染,无副作用) |
| `frontend/.../layouts/G25a.ts` | 不加列。commit 昨天的 key 修复(content/aux_materials/instruments) |

检验行 key = {workshop,step_no,step_name,content,aux_materials,instruments,time_setup,time_per_piece,time_total},与前端 G25a.ts 完全一致。step_no 留空。

### 节点B:契约校验脚本 + guard hook

| 文件 | 改什么 |
|------|--------|
| `scripts/hooks/guard-column-align.py`(新增) | PostToolUse。路径过滤(layouts/*.ts 或模板)→ json.load 后端 chapters[].columns[].key + 正则提前端 chapterCode/dataColumns key → 配对求差集 → 减 KNOWN_DIFFS → 剩余 print 告警 exit 0(warn) |
| `KNOWN_DIFFS`(脚本顶部) | G10a/G14a/G12a 历史不一致,白名单兜底,标 TODO 单独排期 |
| `.claude/settings.local.json` | hooks.PostToolUse 追加注册 guard-column-align.py |

### 节点C:docx2pdf 实测探底 + 固化 skill

taskkill 清 Word → 取装配卡 docx → 带 timeout90 依次测 docx2pdf/win32com/soffice(每方法后 taskkill)→ 记录 → 定方案 → 固化 skill。

## 禁区

- 不动 g25a-perstep 并行核心(Semaphore4/每步一行/n行structured_values假设)
- 不改 G22a(已对齐)
- 不重排前端 G25a 21 列布局
- 不修 G10a/G14a/G12a 历史不一致(白名单)
- 不做生成质量优化

## 验证

- 节点A:`conda run -n gywj --no-capture-output python backend/diagnose_g25a.py` → filled_data 行数>工序数且出现 step_name='检验';回归 `pytest backend/tests/services/test_structured_extractor.py`
- 节点B:故意改错 G25a.ts key→告警;白名单 G10a/G14a/G12a 不报;改无关文件不触发
- 节点C:转真实 docx→PDF 产出正常、无 Word 僵尸累积

## ⚠️ 执行注意

- 新 hook 注册要新 session 才生效(节点B 验证注意)
- 改后端核心代码别信 reload,彻底重启
- conda 环境 = gywj(Python 3.10)
