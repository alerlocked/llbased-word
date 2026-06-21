---
project: localknowledgebase-word
path: D:/Project Nantianmen/projects/localknowledgebase-word
branch: main
updated_at: 2026-06-21T20:21:36+08:00
last_commit: 8e98923
status: G25a 检验工序行 + 前后端契约校验 + docx2pdf 修复（PLAN 8e98923 seal，执行 loop 进行中）
task_state: running
task_slug: contract-align
---

<!--AUTO:GIT-->
## 最近变更
- `8e98923` plan(contract-align): G25a inspection-row + frontend-backend column-key guard + docx2pdf fix (1 second ago)
- `66a633e` docs(config): local qwen3-30b-a3b switch needs dummy API key + diagnose step (25 hours ago)
- `2523a88` chore(g25a-perstep): wrap up done + commit diagnose_g25a.py probe (25 hours ago)
- `8a3a4ef` chore(config): document local qwen3-30b-a3b switch (mindie port 1028) (26 hours ago)
- `d803946` feat(generation): G25a per-step parallel (Semaphore 4, each step one LLM call) (26 hours ago)
- `204c5f8` plan: G25a per-step parallel generation (per-step LLM, semaphore 4) (26 hours ago)
- `3b84ca5` feat(generation): inject profile layers (principles + triples) into G25a prompt (2 days ago)
- `d0f75b6` feat(generation): fix G25a empty content (max_tokens) + source-driven G22a/G25a (2 days ago)
- `9201e85` plan: G25a content empty = LLM max_tokens truncation (v2 root-cause revision) (2 days ago)
- `ae5f010` plan: G25a content writing (fix inject break + profile layers + triples fallback) (2 days ago)
<!--/AUTO:GIT-->

## 当前状态
- **在做**：contract-align（PLAN 8e98923 seal）——G25a 检验工序行 + 前后端 column-key 契约校验 + docx2pdf 修复
- **背景**：G25a 后端生成 inspection(检验)但前端无对应列→丢弃；真实工艺文件检验是单独成行(工序名=检验)。docx2pdf 三方法全挂待修
- **节点进度**：A(后端检验行,方案Y merge后处理) 待做 / B(契约校验+guard hook) 待做 / C(docx2pdf实测+固化skill) 待做
- **节点A方案**：LLM 照常每步生成 content+inspection(不动并行核心)，merge 后 _expand_inspection_rows 拆检验行插入；模板删 inspection 列
- **下一步**：spawn Writer 做节点A(writing_agent slot_keys增补+后处理函数+调用点+step_msg inspection指引+模板删列)
- **（历史）前置 g25a-perstep**：A✅B✅C✅ web验证通过
- **前置完成**：g25a-write 已落地（content空=max_tokens截断已修 d0f75b6/3b84ca5，diagnose实证10/10）
- **本任务**：G25a 每道工序一次 LLM 调用并行（Semaphore 4），解决本地千问3-30B-A3B(2048上限)必截断 + 提质量。云端qwen-plus验证+本地配置留好
- **节点进度**：A ✅(d803946) / B ✅(8a3a4ef) / C ✅web验证通过(g25a_per_step_parallel_done steps=10 slots=20 + localStorage G25a 10行 content + draft_complete 97s)
- **节点C纠正**：之前"g25a-write 前端 localStorage bug"误判——实际是 _test_g25a.py wait 130s 不够(timing)。wait 240s 后 localStorage 正常有 G25a，前端存储 OK
- **待用户**：起本地千问3-30B-A3B(port 1028) 后 .env 切 DASHSCOPE_BASE_URL_COMPLEX/MODEL_TIER_COMPLEX，跑 diagnose 本地实测（预期比云端 129s 快，maxPrefillBatchSize 8）

## 关键决策
- **G25a content 空 = phased 注入断点**（非抽取问题、非偶发）：模板有 generation_phases→必走 phased→G25a 经 template_required 进 missing_chapters 但 _doc_dir="" → 注入点B(orchestrator:2620)无 fallback 直接 continue。修法：复用注入点A 的扫描 fallback（get_all_chapter_indexes 找「装配」章节）
- **行文标准=画像两层**（用户定）：principles 强约束 + preferences 偏好；不引入外部标准文件（QJ903 等）
- **参数参考值=triples 兜底**（用户定）：工步原文优先，原文缺才参考 triples，两者都无留空，绝不臆造
- **G25a 检验=单独工序行（用户定+截图验证）**：检验不单独成列(前端不加列)，改为后端生成检验工序行(step_name=检验,content=检验项)，贴合真实工艺文件格式。方案Y(merge后处理)不动 g25a-perstep 并行核心
- **前后端契约校验=guard hook（用户定）**：PostToolUse warn 脚本对比模板key vs layout key；G10a/G14a/G12a 历史不一致白名单兜底(KNOWN_DIFFS)，本次不修
