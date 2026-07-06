# 需求对齐卡：Step 4 标准强约束（注入 + review 校验）

> slug: `standard-enforce`
> 关联：[[exp-revive-extract-funnel]]（StandardExtractor 已落库 38 条款）、[[exp-profile-expand-and-relations]]
> 范围：Step 4。标准条款（standards/standard_clauses，Step 2 已落库）注入生成 + review_agent 校验「不容有错」。

## 目标

- **注入**：生成时 prompt 含相关标准条款（从 standard_clauses 查 → system_msg），让 LLM 生成时遵守。
- **校验**：生成后 review_agent 比对标准条款，违规标 **ERROR**（「标准不容有错」= 硬约束）。
- **成功**：① 生成 system_msg 含标准条款段（grep 日志）；② review 对违规内容标 ERROR（pass=False）；③ 不引入新 fail。

## 边界

### 做
- **注入**：writing_agent `_do_template_fill` system_msg 加标准条款段（调 C `search_standard_clauses` 查相关条款 → 拼 system_msg）
- **校验**：review_service 加 `_check_standards`（比对生成内容 vs standard_clauses，违规标 ERROR）；`review` 方法调它
- **C 查询**：`search_standard_clauses` 已恢复（Step 2 节点4），直接用

### 不做
- ❌ 重写 StandardExtractor（Step 2 已落库）
- ❌ 改前端 / source-driven 主路径
- ❌ ConditionGroup 注入（profile.knowledge）
- ❌ 软偏好 WritingPreferences
- ❌ colspan content 修复（独立技术债）

## 模糊点（已清零，2026-07-06 对齐）

1. **注入条款**：✅ **chapter_type 过滤 + top_k**（G25a 装配卡 → process 类条款；format 类全局；top_k 限制避免 token 爆）
2. **校验严格度**：✅ **process/quality/safety=ERROR, format=WARNING**（核心诉求「不容有错」针对工艺/质量/安全；格式软约束）
3. **校验方式**：✅ **LLM 判定**（条款 + 内容交 LLM 判违规；准，每章 1 LLM 调用）
4. **注入点**：✅ **_do_template_fill 全章节**（标准章节无关，所有模板章节 system_msg 注入）

→ 模糊点清零，进 PlanMode 写 PLAN。

## 下游

- → `PLAN-standard-enforce.md`（同 slug，模糊点清零后进 PlanMode）
