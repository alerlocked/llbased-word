# 需求对齐卡：source-driven 生成链路贯通（文档索引 + extract 工序 + 有源生成）

> slug: `source-driven-fix` | 项目: localknowledgebase-word | 日期: 2026-07-09
> 承接 gen-quality-fix 节点②深挖结论：文档索引断裂（chapter_indexes=0）致所有章节无源生成。

## 背景

gen-quality-fix 节点②深挖铁证：4 次生成 `chapter_indexes_count=0`（知识库文档未索引），`missing_chapters` = 模板硬编码 10 章节 + `_doc_dir` 全空 → `orchestrator.py:1625 if not doc_dir: source_text=""` → **所有章节无源生成、LLM 凭空编**。这是用户"生成没到位"的真因。

同时 `assembly_process_template.json:308` 硬编码 `process_steps`（12 工序），违背"每次从用户上传文件 extract 工序"的核心（用户明确纠正：12 工序是测试文件的，不是标准，禁止硬编码冒充）。

## 目标

- **解决谁的什么问题**：工艺工程师上传不完整工艺文件，系统应正确提取工序 + 章节源、有源生成合格工艺文件；当前索引链路断、工序疑似硬编码，生成全无源、不达标。
- **成功长什么样**（可观察，对齐工艺文件验收标准 extract 版）：
  1. 上传测试文件（全单电缆装配规程）→ `chapter_indexes > 0`（文档被索引）
  2. G19a 从上传文件 **extract 出真实工序**（非硬编码 process_steps），工序数正确
  3. 各章节**有源生成**（source_text 非空），按验收标准 11 章节达标
  4. 模板 `process_steps` 硬编码清理/降级（G19a 走 `extract_process_steps`）
  5. 后端日志无 `chapter_indexes_count=0`、无无源生成
  6. 验收清单逐项过（G22a step_desc 工序名直填 / G25a content 详实 / 列表章节能反推 / 无会签 / 参数无臆造）

## 边界

**做**：
- 修文档索引链路（上传→解析→`chapter_index`+`materials`→`chapter_indexes>0`）
- G19a 改 `extract_process_steps` 读上传文件，清/降级模板 `process_steps` 硬编码
- 贯通 source-driven（extract 工序+章节源→注入→有源生成）
- 按验收标准验收生成

**不做**：
- 不改 11 章节模板结构（已定）
- 不重写生成主路径（修 extract/索引链路通即可）
- 不做新功能 / 多专业扩展
- 不碰 colspan / derive 4 约束（已修/固化）

## 模糊点

- [PLAN 探查] **文档索引为什么断**：上传→解析→`chapter_index` 建库哪环断（解析产物散落 `data/pages/material_1_*`、`documents/1/` 只剩 vlm/images、`materials` 表空）→ PlanMode 定
- [PLAN 探查] **process_steps 硬编码是不是 G19a 主路径**（git blame `assembly_process_template.json:308` + G19a 生成代码）→ PlanMode 定
- [已确认] **验收标准 extract 版**：G19a 工序 = 从上传 extract（动态），非硬编码（用户已纠正）
- [接受] VLM 解析（mineru）慢/环境相关，验收优先用现有 `data/pages` 解析产物
- [待 PLAN] 上传→`chapter_index` 正确建库流程是已存在没触发，还是缺失 → PlanMode 定

## 下游

→ 进 PLAN（同 slug `source-driven-fix`）：PlanMode 查根因 → 改动清单 → seal。
