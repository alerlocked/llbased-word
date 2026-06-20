# 需求对齐卡：G25a 分工序并行生成

## 目标
- 解决谁的什么问题：
  - 本地千问3-30B-A3B（mindie, maxIterTimes=2048）单次生成 10 工序 content **必截断**（2048 < 需求）；
  - 即使云端 qwen-plus（8192），单次吐一大坨 10 工序 content，质量下降（长输出易跑偏/重复）。
- 方案：G25a 每道工序一次 LLM 调用，**并行（并发 4）**，每个调用专注生成该工序的 content/inspection。
- 成功长什么样：① diagnose content 10/10 非空 ② 质量专业（每工序专注，力矩等参数准、不臆造）③ 并行生效（并发 4，vs 串行加速）④ 本地千问3-30B-A3B endpoint/MODEL 配置留好，起服务后改一行切本地

## 边界
- 做：
  - `writing_agent.is_g25a_sourced` 改「单次 LLM 生成全部」→「每工序一次 LLM 并行循环（Semaphore 4）+ 合并 slots」
  - 本地千问3-30B-A3B 配置：`DASHSCOPE_BASE_URL_COMPLEX` / `MODEL_TIER_COMPLEX` 支持切本地（localhost:1028 / qwen3-30b-a3b），.env 留好
  - diagnose_g25a.py 加并行验证
- 不做：
  - 起 mindie 服务（用户做，port 1028）
  - sub_sections（references/tech_notes/requirements，chapter 级）不分工序，保留单次
  - 非 G25a 章节
  - 前端渲染（另案）

## 模糊点
- [接受的不确定性] sub_sections（references/tech_notes/requirements）是 chapter 级（非 per-row），分工序并行只针对 per-row 的 content/inspection；sub_sections 保留单次生成或并入。执行 loop 定具体。
- [已澄清] 模型：云端 qwen-plus 验证架构 + 本地配置留好（用户起服务后切）
- [已澄清] 并发：4（Semaphore）

## 下游
- → 进 PLAN（slug：g25a-perstep）

## 依据
- 本地千问3-30B-A3B mindie 配置（deploy/mindie/config-2.2rc1-qwen3-30b-a3b.json）：maxIterTimes=2048, maxPrefillBatchSize=8, port 1028
- 当前连云端 qwen-plus（.env 未设本地 endpoint），分工序并行云端先验证
