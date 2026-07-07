# 需求对齐卡：撤 standard-enforce + 建反馈规则学习闭环

> slug: `feedback-rules` | 项目: localknowledgebase-word | 日期: 2026-07-07

## 目标

- **解决谁的什么问题**：用户（工艺工程师）用软件生成装配工艺文件，模型"不够准"，但无人能预先定义"准"的标准——QJ903 标准经实测是前言废话（38 条全前言/safety=0/工艺词召回 0），给不了专业判据。需要在真实使用中，通过用户对生成结果的修改，让系统逐步学会"装配工艺怎么写才算准"。
- **成功长什么样**（可观察）：
  1. 撤 standard-enforce 后，生成 system_msg 不再含 QJ903 前言噪声（注入段消失，可 grep 验证）
  2. 用户改一次装配生成结果 → 系统归纳出可读规则进库 → 下次同类生成注入该规则（端到端闭环可演示）
  3. 用户能在 UI 看到/编辑已学规则（透明，非黑盒）
  - 北极星（不作第一阶段硬指标）：同样的错不犯第二次，用户改得越来越少

## 边界

**做**：
- 撤 standard-enforce：删 `writing_agent` 标准注入段 + `review_service._check_standards`；**保留 review async 架构 + 调用方 await**（async 是好东西）
- 反馈采集：前端编辑器抓用户对生成结果的修改 diff
- LLM 归纳：把修改总结成可读规则（画面 A 被动自动为主 + B 手动触发审改兜底）
- 规则存储：复用 `profile.principles`（已有全章节注入机制，见 exp-profile-expand）
- 注入：下次同类生成注入 system_msg（复用现有 principles 注入点）
- 审查 UI：看/改已学规则

**不做**：
- 多专业扩展（机加/焊接模板、specialty 生成路由）——远期；现在 specialty 只做检索维度
- 模型微调/在线 ML 训练——太重，PMF 阶段不碰
- 纯 case 堆注入（用户已否决，要总结成规则）
- 黑盒记忆（规则必须人可读可改）

## 模糊点

- [已澄清] 撤 standard-enforce（用户决策，实测 QJ903 空转 + 噪声）
- [已澄清] 总结成规则，不堆案例（用户纠正）
- [已澄清] A 被动采集为主 + B 手动触发审改（用户认同，参考 Cursor rules/memories 范式）
- [已澄清] 规则可读可改（透明）
- [已澄清] 现在只装配，远期多专业
- [接受的不确定性] "做准"的终极判据是用户主观体感，无法预先量化；第一阶段以"闭环跑通 + 规则可演示注入 + UI 可审改"为成功标准
- [进 PLAN 探查后定] ① 规则载体：复用 profile.principles vs 新建 learned_rules 表 ② 采集点：编辑器哪个组件（ProcessTableEditor/Tiptap）能抓生成→修改 diff，数据存哪 ③ A 自动总结触发时机（每次生成后/攒 N 次/定时）④ 规则粒度：全局 vs 按章节类型 ⑤ 注入选择性：全注入 vs 按章节类型匹配

## 下游

→ 进 PLAN（同 slug `feedback-rules`）：PlanMode 探查 profile 存储结构 + 编辑器 diff 可行性 + 注入点，定最小可用设计，seal 给用户审。

## 关键约束（给 Writer/Reviewer，pitfalls + 经验页摘）

- **T01** 删除清三层（DB + 文件系统 + 缓存）
- **T02** 禁 `Path(__file__).parent.parent` 跨层路径，路径只在 config 定义
- commit 前查暂存区无敏感数据（.env/db/用户上传）
- **int64 ID JSON.parse 丢精度**——前端按字符串处理
- **sync→async 改造**要同步改所有调用方 + 测试 + skip 参数（exp-standard-enforce / exp-profile-expand 教训）
- 编辑器 diff 采集注意：`editorTemplateData` 未持久化、与 `editorContent` 结构不同（conventions memory 已知问题）
- 反馈学习 fail-soft：归纳/注入任何失败记日志不阻塞生成主流程（同 standard-enforce/profile 的 fail-soft 模式）
