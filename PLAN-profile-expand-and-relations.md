# PLAN: Step 2 尾巴（关联落库）+ Step 3（画像扩全章节 + triples 清洗）

> slug: `profile-expand-and-relations` · 关联 `ALIGN-profile-expand-and-relations.md`
> 用户决策：content 提名匹配关联 / 全章节注入 / 正则修+LLM 校验 / documents/1 重抽
> seal 后不可变。Reviewer 从 git 读本文件。

## Context

两个遗留：① Step 2 尾巴——extract_and_save 不落 relations（StepMaterial/StepTool 空），C 关联查询返空；② Step 3 画像——principles/triples 注入锁在 G25a（is_g25a_sourced gate，历史偶然），triples 30% 噪声（数值贪婪/标准句段残留/工艺泛词）。本步：落关联 + 注入扩全章节 + 清洗 triples + 重抽。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| **`document_profile_learner.py`**（:97-145） | ① qty_patterns 数值组 `[\d\-±~.]+` → `(?:\d+(?:\.\d+)?(?:±\d+(?:\.\d+)?)?)`（禁连续小数点，修 `3.60.4N·m`）；② 标准正则 object 最小语义校验（长度≥3，过滤句段残留）；③ `_guess_current_section` 兜底「工艺」改 None；④ `_score_and_filter` 后加 LLM 校验 triple 合理性 |
| **`profile.py`** learn-file / DocumentProfileLearner | documents/1 重抽（清洗后覆盖 assembly.json 旧 10 条脏数据） |
| **`writing_agent.py`**（:1000-1026） | principles+triples 注入移出 `is_g25a_sourced` gate——抽 `_get_profile_constraint_fragment` 方法，全章节 system_msg 统一调。G25a 原文约束（1027+）保留 gate 内 |
| **`knowledge_extractor.py`** extract_from_doc/save | extract_from_doc 产 relations（G25a content 提物料/工具名 → 匹配 MaterialCatalog.name）；extract_and_save 落 StepMaterial/StepTool |

## 禁区

- ❌ Step 4 标准 review / ConditionGroup 注入 / 软偏好 / 改 G25a 原文约束 / 前端 / source-driven / LLM 模型

## 验证

1. triples 重抽 documents/1：不含 `3.60.4N·m` / `照工艺文件的` / `工艺→力矩`
2. 画像扩：G22a/G14a 生成 system_msg 含画像强约束+参考值
3. 关联：extract_and_save('1') 后 StepMaterial/StepTool > 0；search_materials_for_step 返关联
4. pytest 回归不引入新 fail

## 拆分（节点）

1. **节点1 triples 正则清洗**：document_profile_learner 力矩数值 + 标准 object + current_section
2. **节点2 LLM 兜底校验**：_score_and_filter 后 LLM 校验
3. **节点3 documents/1 重抽**：learn_file 覆盖 + 验干净
4. **节点4 画像扩全章节**：writing_agent 抽 `_get_profile_constraint_fragment` + 移 gate
5. **节点5 关联落库**：extract_from_doc 产 relations + extract_and_save 落 StepMaterial/StepTool
6. **节点6 验证**：triples 干净 + 画像全章节 + 关联 + pytest
