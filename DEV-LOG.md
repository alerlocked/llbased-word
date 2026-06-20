---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-06-20T18:36:52+08:00
last_commit: 204c5f8
status: G25a content 空=LLM层max_tokens截断（PLAN v2 seal，修LLM层+画像注入）
task_state: running
task_slug: g25a-write
---

<!--AUTO:GIT-->
## 最近变更
- `204c5f8` plan: G25a per-step parallel generation (per-step LLM, semaphore 4) (1 second ago)
- `3b84ca5` feat(generation): inject profile layers (principles + triples) into G25a prompt (18 hours ago)
- `d0f75b6` feat(generation): fix G25a empty content (max_tokens) + source-driven G22a/G25a (19 hours ago)
- `9201e85` plan: G25a content empty = LLM max_tokens truncation (v2 root-cause revision) (19 hours ago)
- `ae5f010` plan: G25a content writing (fix inject break + profile layers + triples fallback) (19 hours ago)
- `d18db98` fix(generation): harden 工艺文件 extraction (step9/countersign/step_name) (5 days ago)
- `f747293` feat(retrieval+generation): source-driven 工艺文件生成链路 (6 days ago)
- `9a36e50` fix(generation): robustly filter continuation titles, stop killing codes (9 days ago)
- `ca38a96` fix(editor): drop countersign column and signature row, fix alignment (9 days ago)
- `4a1ff7d` feat(editor): add hover add/delete row toolbar to FallbackTable (9 days ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：G25a 装配工艺卡片「工序内容」撰写机制（PLAN ae5f010 seal，slug=g25a-write）
- **诊断(已闭环)**：素材抽取健康(verify 10工序/52工步)；fill注入OK、merge OK。content空真根因=LLM max_tokens=6000截断→_parse_llm_json None→content空→retry不触发(structured有行)
- **节点进度**：A ✅(d0f75b6) / B ✅(3b84ca5) / C ✅后端铁证完成 — 等用户真实浏览器补齐验证前端渲染
- **节点C验证**：server日志铁证(注入×2 doc_dir=1 + 画像loaded + writing_task_completed装配工艺卡片 + draft_complete 9chapters) + diagnose实证(10/10 content含力矩)。_test_g25a.py G25A_NOT_FOUND=playwright localStorage隔离(memory已知)，非生成问题
- **下一步**：用户真实浏览器补齐验证前端G25a content渲染（playwright测不了）；diagnose_g25a.py 留作回归诊断

## 关键决策
- **G25a content 空 = phased 注入断点**（非抽取问题、非偶发）：模板有 generation_phases→必走 phased→G25a 经 template_required 进 missing_chapters 但 _doc_dir="" → 注入点B(orchestrator:2620)无 fallback 直接 continue。修法：复用注入点A 的扫描 fallback（get_all_chapter_indexes 找「装配」章节）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好；不引入外部标准文件（QJ903 等）
- **参数参考值=triples 兜底**（用户定）：工步原文优先，原文缺才参考 triples，两者都无留空，绝不臆造
