# PLAN: QA 检索提质（同义词扩展 + 失败强约束 + jieba 术语词典）

> slug: `qa-retrieval-quality`（总纲 `dialog-task-pipeline` 第三步）
> seal 后不可变。Reviewer 从 git 读本文件。

## Context（为什么）
QA 问答(`reply-question-stream`)检索靠 `global_keyword_search` 关键词子串匹配(jieba 分词),3 个实证弱点:① 同义词不命中(子串匹配,"车床加工"查不到"车削")② 检索 0 结果时 LLM 无强约束可能编造 ③ jieba 工艺术语分词不准。本步用现有资源(`standard_terms.json` + jieba)提质,**不向量**(2026-06-14 决策勿复活)。

**范围(用户定 A:现有功能提质)**:工艺同义词扩展 + 检索失败强约束 + jieba 术语词典。
> ⚠ 诚实边界:`standard_terms.json` 是工艺术语(车削/铣削),非物料词。同义词扩展对机加工文档有效,对装配文档(当前主用)命中有限。A 的实际价值主要在失败强约束(防编造)+ jieba 分词。物料同义词(密封脂↔密封胶)本期不覆盖。

## 改动清单

### `backend/app/services/hierarchical_context.py`
| 改动 | 说明 |
|------|------|
| 同义词扩展 | `extract_keywords` 后加载 `standard_terms.json` 建 term→alias 反向映射,把关键词扩到同义标准术语;fail-soft |
| jieba 术语词典 | 模块初始化 `jieba` 加载 `standard_terms.json` 术语为自定义词典;JIEBA_AVAILABLE 守卫 + fail-soft |
| 失败标识 | `global_keyword_search` 0 结果时,`build_context` 标识 `retrieval_empty=True` |

### `backend/app/api/agent.py`
| 改动 | 说明 |
|------|------|
| 失败强约束 | `reply_question` material_instruction:检测 `retrieval_empty` 时 prompt 强约束"检索无果,必须说不知道/通识简答标注,禁止编造文档内容" |

## 禁区
- 不向量。`generate-stream`/`draft_complete`/source-driven 主链零改动。review/proofread 不动。物料同义词表本期不建。

## 验证
1. 工艺术语同义词(机加工场景):curl `/reply-question-stream` 问"车床加工参数"(文档写"车削")→ 改后命中;无机加工文档则标注留观察。
2. 检索失败强约束:问库无内容 → LLM 拒答/标注通识(不编造)。
3. 回归:generate-stream + review/proofread 不受影响。
4. pytest 回归(test_hierarchical_context)。

## 下游
验证通过 + commit 后,回总纲对齐第四步。
