# PLAN: Step 4 标准强约束（注入 + review 校验）

> slug: `standard-enforce` · 关联 `ALIGN-standard-enforce.md`
> 用户决策：chapter_type 过滤 + top_k / process·quality·safety=ERROR·format=WARNING / LLM 判定 / 全章节注入
> seal 后不可变。

## Context

StandardExtractor（Step 2）已落库 38 条款，C search_standard_clauses 已恢复。但标准既不注入生成也不校验——「不容有错」无保障。本步：注入（system_msg）+ 校验（_check_standards，LLM 判定，ERROR 硬约束）。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `writing_agent.py` _do_template_fill（画像强约束后 ~1027） | system_msg 加「## 适用标准条款」段：SessionLocal() 调 search_standard_clauses（chapter_type 映射 + top_k 5），拼条款 |
| `review_service.py` | 加 _check_standards（SessionLocal 查 + LLM 判违规 + severity 映射 process/quality/safety=ERROR, format=WARNING）；review 方法调它 |

## chapter_type → clause_type

process_card/assembly_card → process+safety；其他 → format+safety。safety 全局。

## 禁区
- ❌ 重写 StandardExtractor / 改 C search_standard_clauses / ConditionGroup / 软偏好 / 前端 / colspan

## 验证
1. 注入：G25a system_msg 含标准条款段
2. 校验：违规内容 → ERROR（passed=False）；合规不误报
3. pytest 回归

## 节点
1. **节点1 注入**：writing_agent system_msg 加标准条款段
2. **节点2 校验**：review_service _check_standards + review 调
3. **节点3 验证**：注入 + 校验 + pytest
