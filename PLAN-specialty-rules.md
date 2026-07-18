# PLAN: 实施细则固化到画像 + review（分层混合，先 3 专业）

> slug: `specialty-rules` · 对齐卡 `ALIGN-specialty-rules.md` · seal 后不可变

## Context（为什么做）

二八三厂《工艺规程细化量化规范性用语通用实施细则》(`data/工艺规程细化量化规范性用语通用实施细则.wps`) 是工艺文件已总结的细化量化标准，三层结构：①敏感词/模糊词（附录B 33条）②必填量化参数（附录A 带 `*`）③规范用语模板（表1-9 带 XX 占位）。当前系统生成与 review 都不按它执行 → 工艺文件缺量化参数、含模糊词、无标准依据。

现状（已核实）：
- review 是纯规则引擎，`_check_standards`(LLM 校验) 被 v1-cleanup 砍（`review_service.py:215` 注释 `skip until LLM integration`，`_check_data_validity` 同）
- Profile principles/triples 只注入生成（`writing_agent.py:1002-1023`），review 用画像做规则匹配但无 LLM
- **`welding.json`/`coating.json` 不存在**（`backend/data/profiles/` 只有 assembly.json，运行时 `orchestrator.py:708` 回退默认 profile）

目标：把细则按 3 专业（装配 assembly / 焊接 welding / 表面工程≈涂装 coating）固化，review 分层混合（①敏感词规则 ②必填参数 LLM 校验 ③模板注入生成），让工艺文件按细则执行。其余 6 专业留接口、不录数据。

## 数据建模（细则 → Profile）

| 细则层 | 落点 | 形式 |
|---|---|---|
| ① 敏感词/模糊词（附录B） | 新建 `backend/data/compliance/sensitive_words.json`（复用 `compliance_checker.py:46-77` 的 JSON 加载模式，review 侧自己读） | `{word, aliases, scope[专业], fuzzy_example, standard_example}`；命中→WARNING，`fix_hint` 塞 standard_example |
| ② 必填量化参数（附录A 带*） | `Profile.knowledge`（ConditionGroup） | `entity`=工序名(须会出现在文本，因 `_check_knowledge_data:251` 按 entity 命中), `conditions={专业}`, `attributes={参数名:"REQUIRED(示例)"}`；review LLM 判齐全 |
| ③ 规范用语模板（表1-9） | `Profile.principles`（**只落通用+高频 ~10 条**，防 prompt 膨胀） | `dimension/name/description/check_expression/source`；落库后生成期自动注入(`writing_agent.py:1008-1012`) + review 规则匹配 |

**注意**：必填参数落 `knowledge` 不进生成期 principle 段（writing 注入只读 principles+triples，不读 knowledge），知识库数据只在 review 期用——这是防 prompt 膨胀的关键。

## 改动清单（每节点 1 commit，独立可验证）

| 节点 | 文件 | 改什么 | 验证 |
|---|---|---|---|
| **N1 数据 seed** | 新建 `backend/scripts/seed_impl_rules.py`；新建 `data/compliance/sensitive_words.json`；新建 `data/profiles/welding.json`+`coating.json`；追加 `assembly.json` | seed 内含 ConditionGroup(必填参数,~15条)+Principle(模板,~10条)+读敏感词JSON；走 `Profile.add_knowledge/add_principle`(`profile.py:300-346`) 去重，幂等写回；支持 `--domain all` | 手跑 → 3 profile knowledge 非空、`Profile.from_json` 不抛错；重跑条数不变(幂等) |
| **N2 敏感词规则** | `backend/app/services/review_service.py` | 新增 `_check_sensitive_words`(读 JSON，按 domain scope 过滤)；`review()`(L106 后)调用；命中 WARNING+fix_hint。`_check_universal`(L143) 现有 4 个 vague_words 保留作超集 | `pytest -k sensitive`：喂"适量"→WARNING；"拧紧"不误报 |
| **N3 必填参数 LLM 校验** | `backend/app/services/review_service.py` | 新增 `async _check_mandatory_params(content, profile, result, skip_llm)`；`review()` 加 `skip_llm` 参数透传(复用闲置的 L100 `skip_standard_check` 思路)；复用 `_check_knowledge_data`(L244) entity 命中 → 对 `REQUIRED` attributes 调 `llm_service.generate_with_messages(tier="simple")`(范式 `document_profile_learner.py:99-115`)；缺→ERROR `missing_mandatory_param`；fail-soft | pytest `skip_llm=True` 不误报；手跑真实 LLM：缺焊接电流→报 missing_mandatory_param |
| **N4 生成注入验证** | 不改 writing_agent(注入现成) | 仅验证 principles 落库后 `## 画像强约束` 含新原则、生成不含模糊词 | 手跑生成，抓 system_msg + 生成文本过 review 自检 |
| **N5 测试** | `backend/tests/test_review_service.py` | 加 `TestImplRules`(敏感词/skip_llm必填/幂等/正常词不误报)；真实 LLM 用例标 `@pytest.mark.manual` | `pytest test_review_service.py` 全绿(xfail 保留) |

依赖：N1 → (N2,N3 并行) → N4 → N5。

## 禁区

- win10/kylin、PDM 集成（已跳过的 feature）
- 现有画像内容：`assembly.json` 的 principles/triples/graph/frequent_terms 一律保留，seed 只 `add_*`(去重)，不 remove/覆盖；welding/coating 从默认 profile 起步追加
- 其余 6 专业（机加/电装/复材/增材/检测/电气互联）只留接口（seed `--domain`、词表 `scope` 字段），不录数据
- 不动 ComplianceAgent / `compliance_checker.py`（敏感词 JSON 共享数据文件，不共享代码路径）
- 不改 review() 现有 4 个 `_check_*` 方法行为，只新增方法；现有 xfail 测试保持
- 不做细则修订流程

## 风险兜底

- **LLM fail-soft 空转**：失败留 INFO issue `mandatory_param_check_skipped` + `logger.warning`，不阻塞（passed 不变，与"没装这功能"行为一致）
- **skip_llm 测试**：CI 无 key 用 `skip_llm=True`；真实 LLM 用例 `@pytest.mark.manual` 不进 CI
- **敏感词误报**：词表只收纯模糊词（少量/少许/适量/适当/尽量/大约/左右/薄薄一层/稍紧/较轻/大的气泡/一段时间后/搅拌均匀/必要时也可…）；**"拧紧/稍紧"等需量化的动作词走 N3 必填参数检查，不进敏感词表**（避免正常描述误报）
- **prompt 膨胀**：principle 只 ~10 条；必填参数落 knowledge 不进生成 prompt；敏感词不进 prompt 只 review 匹配
- **welding/coating.json 缺失**：N1 seed 必须创建，验证含"文件存在 + from_json 不抛错"

## 验证（端到端）

1. `python -m backend.scripts.seed_impl_rules --domain all`
2. `pytest backend/tests/test_review_service.py`（skip_llm 用例全绿，xfail 保留）
3. 手跑（manual）：缺焊接电流的 TIG 工序 → 报 missing_mandatory_param；参数齐全 → 不报；含"适量"→WARNING + fix_hint 标准范例
4. 生成端到端：触发装配/焊接生成 → system_msg 含新原则 + 生成文本过 review 无模糊词 WARNING

## 复用点速查（file:line）

- profile 去重 `add_knowledge`/`add_principle`：`profile.py:300-346`
- review 引擎(已 async)：`review_service.py:95-121`；entity 命中 `_check_knowledge_data:244-265`
- 闲置参数 `skip_standard_check`：`review_service.py:100`
- LLM fail-soft 范式：`document_profile_learner.py:99-115`；单例 `llm_service.generate_with_messages(tier="simple", temperature=0.1)`
- writing 注入 principles+triples：`writing_agent.py:1002-1023`
- profile 启动加载：`orchestrator.py:336`；review 传 profile：`orchestrator.py:701-712`
- compliance JSON 加载模式（数据共享参考）：`compliance_checker.py:46-77`
