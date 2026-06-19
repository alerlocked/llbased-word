---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-06-19T23:27:48+08:00
last_commit: ae5f010
status: G25a content 空=LLM层max_tokens截断（PLAN v2 seal，修LLM层+画像注入）
task_state: running
task_slug: g25a-write
---

<!--AUTO:GIT-->
## 最近变更
- `ae5f010` plan: G25a content writing (fix inject break + profile layers + triples fallback) (0 seconds ago)
- `d18db98` fix(generation): harden 工艺文件 extraction (step9/countersign/step_name) (4 days ago)
- `f747293` feat(retrieval+generation): source-driven 工艺文件生成链路 (5 days ago)
- `9a36e50` fix(generation): robustly filter continuation titles, stop killing codes (8 days ago)
- `ca38a96` fix(editor): drop countersign column and signature row, fix alignment (8 days ago)
- `4a1ff7d` feat(editor): add hover add/delete row toolbar to FallbackTable (8 days ago)
- `75b7c96` feat(editor): add/delete step buttons on FlowChartEditor (G19a) (8 days ago)
- `4878260` feat(editor): hover toolbar for add/delete row and vertical merge (8 days ago)
- `7aad493` feat(editor): render merged cells and align parse with merge state (8 days ago)
- `a6d4707` feat(editor): add mergeUtils with pure cell-merge helpers (8 days ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：G25a 装配工艺卡片「工序内容」撰写机制（PLAN ae5f010 seal，slug=g25a-write）
- **诊断**：素材抽取健康（verify_g25a.py 实测 material id=1 返回 10工序/52工步）；content 空根因=phased 模式注入点B(orchestrator:2620)无fallback直接continue→assembly_steps不注入→is_g25a_sourced=False→退化普通LLM路径
- **节点进度**：A 修LLM层max_tokens截断（进行中）/ B 接画像两层+triples / C web补齐模式实测+G22a直填
- **根因(已锁定)**：fill模式注入OK(注入点A+fallback+verify+memory is_g25a_sourced=True)、merge层OK。真根因=LLM层max_tokens=6000截断(G25a 10工序×多long_text)→_parse_llm_json返回None→content空→sparse retry不触发(structured有行item_count>0)。generate_with_messages不返回finish_reason
- **下一步**：节点A——llm_service返回finish_reason + writing_agent G25a max_tokens 8192 + 截断检测retry

## 关键决策
- **G25a content 空 = phased 注入断点**（非抽取问题、非偶发）：模板有 generation_phases→必走 phased→G25a 经 template_required 进 missing_chapters 但 _doc_dir="" → 注入点B(orchestrator:2620)无 fallback 直接 continue。修法：复用注入点A 的扫描 fallback（get_all_chapter_indexes 找「装配」章节）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好；不引入外部标准文件（QJ903 等）
- **参数参考值=triples 兜底**（用户定）：工步原文优先，原文缺才参考 triples，两者都无留空，绝不臆造
