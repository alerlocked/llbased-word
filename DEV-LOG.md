---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-06-20T18:46:25+08:00
last_commit: 8a3a4ef
status: G25a 分工序并行生成完成（per-step LLM 验证通过，等本地千问3-30B-A3B 实测）
task_state: done
task_slug: g25a-perstep
---

<!--AUTO:GIT-->
## 最近变更
- `8a3a4ef` chore(config): document local qwen3-30b-a3b switch (mindie port 1028) (1 second ago)
- `d803946` feat(generation): G25a per-step parallel (Semaphore 4, each step one LLM call) (2 minutes ago)
- `204c5f8` plan: G25a per-step parallel generation (per-step LLM, semaphore 4) (10 minutes ago)
- `3b84ca5` feat(generation): inject profile layers (principles + triples) into G25a prompt (19 hours ago)
- `d0f75b6` feat(generation): fix G25a empty content (max_tokens) + source-driven G22a/G25a (19 hours ago)
- `9201e85` plan: G25a content empty = LLM max_tokens truncation (v2 root-cause revision) (19 hours ago)
- `ae5f010` plan: G25a content writing (fix inject break + profile layers + triples fallback) (19 hours ago)
- `d18db98` fix(generation): harden 工艺文件 extraction (step9/countersign/step_name) (5 days ago)
- `f747293` feat(retrieval+generation): source-driven 工艺文件生成链路 (6 days ago)
- `9a36e50` fix(generation): robustly filter continuation titles, stop killing codes (9 days ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：G25a 分工序并行生成（PLAN 204c5f8 seal, slug=g25a-perstep）
- **前置完成**：g25a-write 已落地（content空=max_tokens截断已修 d0f75b6/3b84ca5，diagnose实证10/10）
- **本任务**：G25a 每道工序一次 LLM 调用并行（Semaphore 4），解决本地千问3-30B-A3B(2048上限)必截断 + 提质量。云端qwen-plus验证+本地配置留好
- **节点进度**：A ✅(d803946) / B ✅(8a3a4ef) / C ✅web验证通过(g25a_per_step_parallel_done steps=10 slots=20 + localStorage G25a 10行 content + draft_complete 97s)
- **节点C纠正**：之前"g25a-write 前端 localStorage bug"误判——实际是 _test_g25a.py wait 130s 不够(timing)。wait 240s 后 localStorage 正常有 G25a，前端存储 OK
- **待用户**：起本地千问3-30B-A3B(port 1028) 后 .env 切 DASHSCOPE_BASE_URL_COMPLEX/MODEL_TIER_COMPLEX，跑 diagnose 本地实测（预期比云端 129s 快，maxPrefillBatchSize 8）

## 关键决策
- **G25a content 空 = phased 注入断点**（非抽取问题、非偶发）：模板有 generation_phases→必走 phased→G25a 经 template_required 进 missing_chapters 但 _doc_dir="" → 注入点B(orchestrator:2620)无 fallback 直接 continue。修法：复用注入点A 的扫描 fallback（get_all_chapter_indexes 找「装配」章节）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好；不引入外部标准文件（QJ903 等）
- **参数参考值=triples 兜底**（用户定）：工步原文优先，原文缺才参考 triples，两者都无留空，绝不臆造
