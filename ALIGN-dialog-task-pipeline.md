# 需求对齐卡:把对话模式下的任务分配 + 执行链路做完整

> slug: `dialog-task-pipeline`
> 现状调研据代码实测(2026-07-30),见文末「现状证据」。

## 目标

- **解决谁的什么问题**:工艺人员在前端对话里下任务,系统应能可靠识别意图、分配到正确的执行链路并跑通。现状只有「生成/补齐/问答」三类通,「局部修改/审查/校对」要么断、要么没入口,意图识别靠关键词正则误判多。
- **成功长什么样(可观察)**:
  1. **意图识别**:一批对话用例(每类 N 条)正确分流到对应链路,准确率达约定阈值(待拍)。
  2. **局部修改**:对话说「把工序5的力矩改成 X」→ 定位 + 改 + 回传,前端表格可见改后值。
  3. **审/校**:前端触发 → review/proofread agent 真跑 → 问题清单回前端。
  4. **QA 提质**:问答召回/回答质量提升(可观察标准待拍)。
  5. **回归**:现有 generate/fill 不破坏(全量 pytest + web 冒烟)。

## 边界

### 硬约束(用户 2026-07-30)
- **不能影响 generate/fill 补齐主链**:所有改动绕开 `generation_mode shortcut`(orchestrator.py:510)→`_handle_draft_complete`→`continue_conversation`→`_execute_draft_modification` 这条主链;改意图识别/调度时 shortcut 优先级不变,generate/fill 行为零回归。
- **基于现有功能增量改**:不重写活链路(source-driven 生成、functional agent review/proofread、HierarchicalContext 检索全部复用),只接通/补全/清理。
- **一步步走**:4 块不并行铺开,一块一个 lead 小循环(对齐→PLAN→执行→验证),做完一块验证通过再开下一块;每块独立 commit + 回归。

### 做
- 意图识别 LLM 化(`detect_mode` + `intent_recognizer` 关键词正则 → LLM 分类)
- 对话式局部修改执行链路(定位 + 增量改 + 回传)
- 对话式审查/校对链路(前端入口 + 接通 functional agent review/proofread)
- QA 检索提质(reply-question-stream)
- 清理死代码(`_select_workflow`/`execute_workflow`/4 workflow)+ 修 ARCHITECTURE.md 对齐代码

### 不做
- ❌ 恢复向量检索/SearchAgent(2026-06-14 决策勿复活,结构化表格不适用)
- ❌ 阶段1 并发多终端部署(VISION 阶段1,另立项)
- ❌ 重写 source-driven 生成主链(G25a/G19a 等,已是质量主链,只复用不改)
- ❌ 前端大改版(只在 AIChatPanel 加入口/调整,不重构)

## 模糊点(进 PLAN 前清零)

### A. LLM 意图识别的「意图集」最终是哪几种?(★ 根,其他几块的分配基础)
- **现象**:现状 `intent_recognizer` 11 类枚举与下游(`_dispatch` mapping / `_select_workflow`)词汇表对不上,大量落 unknown。
- **问题**:改 LLM 后意图集要重新定,它决定 LLM 输出 schema 和下游调度映射。
- **方案(推荐 A1)**:意图集对齐「前端入口 + 下游 agent」,收敛为 6 类:`generate`(整文件生成)/ `fill`(补缺失章节)/ `qa`(问答检索)/ `edit_local`(局部修改)/ `review`(审查)/ `proofread`(校对)。下游 mapping 同步重写。
  - A2:保留更细粒度(如 review 拆 compliance/rationality)——更准但调度复杂。
  - **推荐 A1**:6 类够覆盖前端任务,且每类直连一个明确下游。

### B. 「对话式局部修改」的边界——定位与改法(★ 最复杂)
- **现象**:现状不带 mode 的 write 输入走意图识别→decompose→dispatch 落 unknown。
- **问题**:「改工序5的力矩」要①识别为 edit_local ②定位到 G25a 工序5的力矩单元格 ③增量改(不是整章重生成)④回传。定位和改法是难点。
- **方案**:
  - B1(推荐先做):**字段/单元格级定位**——用户指定「章节+行键+列」(如「G25a 工序5 力矩」),系统定位 cell 走 LLM 改单值。范围小、可观察。
  - B2:**自然语言整段改**——用户说「工序5写详细点」,系统定位整行 content 重生成。范围大、易跟 source-driven 冲突。
  - **推荐 B1 先行**,B2 视效果再议。需用户确认:改的对象是已生成表格的 cell,还是 free-form 文本?

### C. 「对话式审/校」前端入口形态 + 对象
- **现象**:前端 AIChatPanel 只有 generate/fill 按钮 + 输入框,无审/校入口;后端 functional agent review/proofread 活的、`_dispatch` mapping 也有,只差接线。
- **问题**:入口怎么加?审查/校对的对象是谁?
- **方案(推荐 C1)**:AIChatPanel 加「审查/校对」按钮(对齐 generate/fill 模式),对象 = 当前编辑器内容(editorContent/editorTemplateData),走 generate-stream 识别为 review/proofread → 调对应 agent → 问题清单 SSE 回前端。
  - C2:纯自然语言触发(「审查一下」),无独立按钮——依赖意图识别,入口隐蔽。
  - **推荐 C1**:按钮入口显式、可观察,跟现有 generate/fill 一致。

### D. QA 检索提质的「提质」标准
- **现象**:`reply-question-stream` 走 hierarchical_context 关键词(jieba 分词)+ `_multi_pass_retrieval` 多轮,活但靠关键词,同义词/语义召回弱。
- **问题**:提质指什么?可观察标准?
- **方案**:
  - D1(推荐):**检索提质**——扩同义词/章节结构命中(沿用 HierarchicalContext,不向量),配一批 QA 用例看召回提升。
  - D2:**回答质量提质**——改 qa system prompt / 改 LLM。
  - **推荐 D1**:检索是根,回答 prompt 现状已不错(见 agent.py:126)。

### E. 顺序与依赖(建议,非模糊点)
推荐顺序:① 清死代码+修 ARCHITECTURE(扫障眼,低风险)→ ② 意图识别 LLM 化(分配根)→ ③ 审/校链路(基础好,接线上)→ ④ 局部修改(最复杂)→ ⑤ QA 提质。每块独立 commit,可分节点验证。

### F. VISION 验收
本次属 VISION 阶段0(单机生成链路打通)延伸——把「对话交互链路」补全。建议把可观察验收(用例准确率/局部修改/审校 回传)补进 VISION 阶段0,经用户确认。

## 下游 / 推进
- 总纲 slug `dialog-task-pipeline`,按 E 顺序,**一块一块走**(每块独立 PLAN + 验证,不自主连跑 4 块)。
- 第一步待用户拍,定后进 PlanMode 出第一块 PLAN。

---

## 现状证据(代码实测 2026-07-30)

**前端入口**(`frontend/src/components/AICreation/AIChatPanel.tsx`):仅 generate/fill 两按钮 + 输入框;`generationMode: 'generate'|'fill'|null`(:66)→ `generation_mode`(:520)。无审/校/修改入口。

**后端链路**:
- `process_intent`(orchestrator.py:450)→ generation_mode shortcut(:510)/draft_complete(:529)→ `_handle_draft_complete`→`continue_conversation`(agent.py:1013)→`_execute_draft_modification`(:1629)= **生成主链,活**。
- 第三分支(:543)→`task_decomposer.decompose`→`_dispatch_to_sub_agent`(:674):`document_generation`/`user_confirmation` 不在 agent_mapping → `status:unknown`(:777)= **断**。
- `_select_workflow`(:779)/`execute_workflow`(:808)/`workflows`(:298)/4 workflow = **全 backend 0 调用,死代码**;ARCHITECTURE.md §2 仍当活的写=**文档腐烂**。
- `reply-question-stream`(agent.py:525)→`hierarchical_context.build_context`+`global_keyword_search`+`_multi_pass_retrieval`= **QA 检索,活但关键词**。
- `detect_mode`(agent.py:93)+`intent_recognizer`(11 类)= **关键词正则,非 LLM**。
- functional agent review/proofread 活(registry 注册),`_dispatch` mapping 有 review/proofread 映射,只差前端入口 + 意图接线。
