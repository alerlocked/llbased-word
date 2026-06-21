# 需求对齐卡:G25a content 详实化(extract 链路 + 生成展开 + 开头说明)

## 目标
- 解决谁的什么问题:G25a 装配卡 content 单薄(生成 ~80字/工序 vs 真实工序多段详实)。用户强调"解析-检索链路一定要确保拿到完整信息"。
- 成功长什么样:① G25a 每工序 content 详实(基于源 substeps 展开,非一句概括)② 单薄工序(op5 extract 仅9字 / op9 49字)补足 ③ 装配卡开头说明("本工艺用于指导...")生成。

## 诊断(对照实证)
- G25a 源 18021字(含表格结构/表头,真实工序内容待 PlanMode 厘清)→ extract `assembly_steps` **1134字**(10工序总和)→ 生成 ~80字/工序
- **extract 丢大量内容**;op5 extract 仅 9字(1 substep)、op9 49字 → **截图工序5/9 单薄的根因是 extract 没抽到,非 LLM**
- 装配卡开头"本工艺用于指导..."说明未生成(源开头是表格 header,说明文字位置待查)
- extract 链路(PDF→content.html→assembly_steps)是第一瓶颈(用户钦定链路完整性)

## 边界

### 做
1. **extract 链路完整性**:修 extract 抽全每工序内容(尤其 op5/op9 抽空),确保 PDF→extract 拿全
2. **生成层 content 展开**:prompt 让 LLM 详实展开源 substeps(操作+参数+材料+检验分段写),非一句概括
3. **装配卡开头说明**(前序内容)

### 不做(挡 scope creep)
- **绝不臆造**(基于源 substeps 展开,triples 兜底铁律)
- 其他章节(G14a/G12a 等)单薄 = 后续 lead
- 不推翻 contract-align / content-quality 已落地机制(检验行/检验数量/契约 guard)

## 模糊点
- extract 修复深度:是 `extract_assembly_steps`(工序抽取逻辑)问题,还是更上游(content.html 表格解析 colspan/rowspan,memory 待办"清单错列")?**PlanMode 探索定**
- 18021 含表格结构:真实工序内容到底多少?extract 真实丢多少?**PlanMode 厘清**

## 下游
- → 进 PLAN(slug=content-detail)
