# PLAN: 画像来源标注 + 生成工艺文件附参考资料（source-visibility）

## 改动清单

| # | 文件 | 改什么 |
|---|------|--------|
| N1 | `backend/app/services/document_profile_learner.py` | `_add()` 签名加 `source_doc`，条目写 `source_doc=document_id`；调用点经闭包/参数传入（learn_from_content 的 document_id 下沉到条目级）。merge dedup 键（s\|r\|o 含值）不动 |
| N1 | `backend/tests/test_document_profile_learner.py` | +断言：learn 后 triples 条目带 `source_doc == document_id` |
| N2 | `backend/app/api/agent.py` | draft_complete 产物组装层：project_id → get_project_source_ids → 查 Material.name → chapters 末尾 append `ChapterData("REF", "参考资料", table_type="text", field_values={"content": 素材名文字块})`；markdown 路径追加 `## 参考资料`。source_ids 空 → 不附 |
| N3 | 数据操作（产物 `.test-runs/source-visibility/`） | 画像清 triples/frequent_terms/source_document_ids（保留 principles），learn-file doc1+doc2 重学带来源；KG 不动 |
| N4 | 验证节点（条件性改前端） | 真实生成 ×2：SSE result 含 REF 章节+素材名正确、前端渲染确认（截图）。若前端无 text 渲染分支 → 补一个渲染分支 |

## 禁区

- `backend/app/agents/orchestrator/orchestrator.py`（本次零接触）
- `hierarchical_context.py` / 检索注入链
- principles 内容 / 画像注入语义（方案 B 全量，writing_agent 零改动）
- 学习入口（冻结）
- 前端除 N4 条件分支外零改动

## 验证

- `python -m pytest tests/test_document_profile_learner.py tests/test_profile.py -q`
- 全量 `python -m pytest tests/ -q` 零回归
- 真实链路：generate-stream ×2 → REF 章节素材名正确 → 前端截图渲染确认 → triples source_doc 抽查归位
