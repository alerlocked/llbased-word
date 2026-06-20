---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-06-20T18:44:26+08:00
last_commit: d803946
status: G25a 分工序并行生成（per-step LLM, semaphore 4, PLAN 204c5f8）
task_state: running
task_slug: g25a-perstep
---

<!--AUTO:GIT-->
## 最近变更
- `d803946` feat(generation): G25a per-step parallel (Semaphore 4, each step one LLM call) (0 seconds ago)
- `204c5f8` plan: G25a per-step parallel generation (per-step LLM, semaphore 4) (8 minutes ago)
- `3b84ca5` feat(generation): inject profile layers (principles + triples) into G25a prompt (19 hours ago)
- `d0f75b6` feat(generation): fix G25a empty content (max_tokens) + source-driven G22a/G25a (19 hours ago)
- `9201e85` plan: G25a content empty = LLM max_tokens truncation (v2 root-cause revision) (19 hours ago)
- `ae5f010` plan: G25a content writing (fix inject break + profile layers + triples fallback) (19 hours ago)
- `d18db98` fix(generation): harden 工艺文件 extraction (step9/countersign/step_name) (5 days ago)
- `f747293` feat(retrieval+generation): source-driven 工艺文件生成链路 (6 days ago)
- `9a36e50` fix(generation): robustly filter continuation titles, stop killing codes (9 days ago)
- `ca38a96` fix(editor): drop countersign column and signature row, fix alignment (9 days ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：G25a 分工序并行生成（PLAN 204c5f8 seal, slug=g25a-perstep）
- **前置完成**：g25a-write 已落地（content空=max_tokens截断已修 d0f75b6/3b84ca5，diagnose实证10/10）
- **本任务**：G25a 每道工序一次 LLM 调用并行（Semaphore 4），解决本地千问3-30B-A3B(2048上限)必截断 + 提质量。云端qwen-plus验证+本地配置留好
- **节点进度**：A is_g25a_sourced 分工序并行（进行中）/ B 本地配置留好 / C diagnose+web验证
- **下一步**：节点A——writing_agent is_g25a_sourced 注入点:920 分流，新增 _generate_g25a_per_row_parallel（Semaphore4+gather，每工序一次LLM）

## 关键决策
- **G25a content 空 = phased 注入断点**（非抽取问题、非偶发）：模板有 generation_phases→必走 phased→G25a 经 template_required 进 missing_chapters 但 _doc_dir="" → 注入点B(orchestrator:2620)无 fallback 直接 continue。修法：复用注入点A 的扫描 fallback（get_all_chapter_indexes 找「装配」章节）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好；不引入外部标准文件（QJ903 等）
- **参数参考值=triples 兜底**（用户定）：工步原文优先，原文缺才参考 triples，两者都无留空，绝不臆造
