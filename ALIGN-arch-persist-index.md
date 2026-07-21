# 需求对齐卡:架构单一源 + P1-2 持久化 + P1-1 索引

> slug: `arch-persist-index` · 项目: localknowledgebase-word · 2026-07-21

## 背景(用户定)
三件一次做,P1-3(本地千问)弃:
1. **架构固定一个文件**(ARCHITECTURE.md),DEV-LOG/CLAUDE.md 等别处不乱重复架构
2. **P1-2 editorTemplateData 刷新丢**(用户痛点)——先验证再改
3. **P1-1 catalog ~1s 阻塞**——standard_code 加索引为主

## 现状(Explore + 本轮确认)
- **架构**:无 ARCHITECTURE.md,散在 `CLAUDE.md:35-93`(Agent 系统/目录/4层上下文/数据存储)+ 代码。多层 Agent:用户→Orchestrator→意图识别→Agent(Writing/Review/Proofread/Search/Compliance)→SSE;前端 React+Zustand(persist)+Tiptap。
- **P1-2**:`creationStore.ts:401-404` persist 无 partialize(默认全存含 `editorTemplateData`)。清空只在项目切换(`WorkspacePage.tsx:187`,正常)。**无刷新清空逻辑** → 刷新丢疑 **localStorage 5MB 配额爆**(StructuredDocument 多章节 filled_data 大)或序列化问题。需实测验证。
- **P1-1**:`MaterialCatalog`(database.py:376-390)`standard_code`(385)**无 index**。`_enrich_names_from_catalog`(orchestrator.py:1014)G18a 同步循环 33 次 `find_material_by_code` → `db.query.first()` by standard_code 全表扫 → ~1s。

## 目标 / 成功标准
1. `ARCHITECTURE.md` 为架构唯一源;CLAUDE.md/DEV-LOG 不重复架构(指针)
2. P1-2:刷新后 editorTemplateData 不丢(表格保留,不退化为 JSON 文本)
3. P1-1:G18a catalog enrich 明显加速(加索引,全表扫→索引查)

## 边界
**做**:ARCHITECTURE.md + CLAUDE.md 架构段处理 / P1-2 验证+修 / P1-1 standard_code 加索引(+ offload 待定)
**不做**:P1-3 本地千问 / 数据迁移 / 前端架构重构

## 模糊点(待对齐)
1. **任务1 CLAUDE.md 架构段**:全移 ARCHITECTURE.md + CLAUDE.md 留指针 vs CLAUDE.md 留简架构
2. **任务2 修法**(验证后定,先问倾向):IndexedDB / 后端 API / partialize
3. **任务3 范围**:只加索引 vs 索引 + async offload vs 索引 + 批量查询

## 下游
→ PlanMode:任务2 先验证(localStorage 实际)+ 定三件改点
