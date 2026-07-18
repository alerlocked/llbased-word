# 需求对齐卡：实施细则固化到画像 + review（分层混合，先 3 专业）

> slug: `specialty-rules` · 贯穿 ALIGN → PLAN → .test-runs

## 背景

《工艺规程细化量化规范性用语通用实施细则》(`data/工艺规程细化量化规范性用语通用实施细则.wps`) 是二八三厂工艺文件已总结的细化量化标准。当前系统生成/审查都不按它执行 → 工艺文件缺量化参数、含模糊词、质量无标准依据。

## 目标

- **解决谁的什么问题**：让生成和 review 都按实施细则执行，工艺文件细化量化有据可依。
- **成功长什么样（可观察）**：
  1. 装配/焊接/表面工程 3 个专业画像含细则的「必填量化参数清单」+「规范用语模板」
  2. 生成按模板细化（不再出现"少许/适量/是否/大致/可能"等模糊词）
  3. review 能：① 规则检出敏感词/模糊词 ② LLM 检出"必填参数缺失"——喂一段缺"焊接电流"的焊接工序 → 报「缺必填参数：焊接电流」

## 边界

**做**：
- 扩展 3 个专业画像（映射：`assembly`=装配 / `welding`=焊接 / `coating`=涂装≈细则表面工程喷漆部分）：从细则表1-9 + 附录A 抽「必填参数清单」+「规范用语模板」，落 `Profile.principles` / `knowledge`(ConditionGroup)
- review 分层混合：
  - ① 敏感词/模糊词 → 规则匹配（扩 `review_service._check_universal` + 附录B 敏感词表）
  - ② 必填参数齐全 → **LLM 语义校验**（补回 v1-cleanup 砍掉的 review LLM 半）
  - ③ 规范用语模板 → 注入生成 `writing_agent` system_msg（现成机制）
- 仅主仓 `localknowledgebase-word`

**不做**（挡 scope creep）：
- 不扩 domain 到 9 个（机械加工/工艺检测/复合材料/电气互联/增材制造 → 后续按需，本次留可扩展接口）
- 不改 win10 / kylin（后续镜像同步，见 win10 DEPLOY.md 镜像原则）
- 不覆盖现有画像内容，只**追加**细则条款
- 不做细则自身的「修订流程」机制（细则末章 §修订 非本次范围）

## 模糊点

1. .wps 读取 → **已解决**：pywin32 COM 转 docx 提取，干净版 `data/_impl_rules.txt`（41k 字）
2. review 与画像关系 → **已澄清**：review 现状用画像 principles 做**规则匹配**、无 LLM（`_check_standards` 被 v1-cleanup 砍，`review_service.py:215` 注释 `skip until LLM integration`）；本次补 LLM 校验半
3. 专业维度 → **已澄清**：`domain` 即"专业"；范围 = 先做对得上的 3 个
4. review 方式 → **已定**：分层混合（①规则 ②LLM ③注入）
5. 仓库范围 → **已定**：仅主仓
6. 细则全量未读（已读 2276/3040，附录A.7 装配 + 附录B 敏感词清单未读全）→ **接受的不确定性**：PLAN 阶段精读，尤其附录B（规则检测直接输入）。不阻塞方向
7. 现有画像内容融合方式 → **接受的不确定性**：倾向追加不覆盖；PLAN 看 `data/profiles/assembly.json` 现状定
8. review LLM 校验具体接法（补 `_check_standards` vs 新建 / 接 ReviewService vs ReviewAgent）→ **接受的不确定性**：方向 = 补 `review_service` 的 LLM 校验半；PLAN 设计
9. 表面工程(细则) vs 涂装 coating(现有) 范围差 → **接受的不确定性**：表面工程比涂装广，PLAN 定本次只取喷漆/喷涂对得上的部分

## 下游

→ 进 PLAN-specialty-rules（同 slug）
