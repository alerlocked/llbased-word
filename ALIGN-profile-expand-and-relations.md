# 需求对齐卡：Step 2 尾巴（关联落库）+ Step 3（画像扩全章节 + triples 清洗）

> slug: `profile-expand-and-relations`
> 关联：[[exp-revive-extract-funnel]]（Step 2 主体）、[[exp-derive-strong-node]]（画像 G25a-only 历史偶然）
> 范围：Step 2 遗留尾巴（StepMaterial/StepTool 关联）+ Step 3 画像注入扩全章节 + triples 清洗。Step 4（标准 review 校验）后续单独 lead。

## 目标

- **Step 2 尾巴**：extract_and_save 落 relations（工序→物料/工具关联），让 C 的 search_tools_for_step/search_materials_for_step 返真实关联（不再空）。
- **Step 3 画像**：① principles/triples 注入从 G25a 扩到全章节（移 is_g25a_sourced gate）；② 清洗 triples 30% 噪声（数值贪婪 `3.60.4N·m` / 垃圾边 `照工艺文件的` / 串行错位 `工艺→力矩`）。
- **成功长什么样**：① 上传文档 → extract_and_save 落 StepMaterial/StepTool 关联（行数 > 0）；C search_materials_for_step 返回关联物料；② G22a/G14a 等非 G25a 章节生成时 prompt 含 principles+triples；③ 重新抽 documents/1 的 triples，噪声（数值错/垃圾边）消失。

## 边界

### 做
**Step 2 尾巴**：
- `extract_from_doc` 产 relations（工序 content 提物料/工具名 → 匹配 MaterialCatalog）
- `extract_and_save` 落 StepMaterial/StepTool

**Step 3 画像**：
- writing_agent principles/triples 注入移出 is_g25a_sourced gate（全章节），抽成 `_get_profile_constraint_fragment` 方法（参照 `_get_preference_prompt_fragment`）
- document_profile_learner triples 清洗：力矩正则 `[\d\-±~.]+` 改禁止连续小数点；标准正则 object 最小语义校验（长度≥3，非句段残留）；_guess_current_section 兜底不返回泛词「工艺」

### 不做
- ❌ Step 4 标准强约束（StandardExtractor 注入 + review 校验）—— 下一 lead
- ❌ ConditionGroup 注入（profile.knowledge）—— 数据已落库但注入链路长，留 Step 4 一起
- ❌ 软偏好 WritingPreferences（confidence=0，要 iteration diff 积累，独立任务）
- ❌ 改前端 / 改 source-driven 主路径 / 改 LLM

## 模糊点（已清零，2026-07-06 对齐）

1. **关联匹配**：✅ **content 提名匹配**——G25a 工序 content 提物料/工具名 → 匹配 MaterialCatalog.name，落 StepMaterial/StepTool
2. **画像扩范围**：✅ **全章节注入**——principles/triples 移出 is_g25a_sourced gate，所有 LLM 生成章节注入
3. **triples 清洗**：✅ **正则修 + LLM 校验**——正则修已知噪声（力矩数值贪婪 / 标准句段残留 / 工艺泛词）+ LLM 兜底校验 triple 合理性
4. **重抽**：✅ **documents/1 重抽**——清洗后调 learn_file 重新抽取，覆盖旧脏数据（assembly.json 现有 10 条含噪声）

→ 模糊点清零，进 PlanMode 写 PLAN。

## 下游

- → `PLAN-profile-expand-and-relations.md`（同 slug，模糊点清零后进 PlanMode）
