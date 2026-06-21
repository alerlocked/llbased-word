# PLAN: G25a content 详实化(extract colspan + 生成展开 + 开头说明)

> seal 后不可变。Reviewer 从 git 读本文件比对 diff。slug=content-detail。

## Context
G25a content 单薄(~80字/工序 vs 真实多段详实)。实证三层根因:① `_table_to_markdown` 不展开 colspan/rowspan → op5 工步文本被 pad 吞(extract 仅 9字,ASM_TOTAL 1134)② step_msg "1-2句概括"→ LLM 概括 ③ 装配卡开头说明没拿。用户:extract 链路完整性 + 生成详实 + 开头说明,**绝不臆造**。

## 改动清单

### 节点1(核心,前置):_table_to_markdown colspan/rowspan 网格展开
| 文件 | 改什么 |
|------|--------|
| `hierarchical_context.py:1225-1278` `_table_to_markdown` | 重写二维网格展开(rowspan 纵向占位 + colspan 横向填 N 列,每 td 归位正确列),保留后处理(`_scrub_audit`/删签名行/删全空行) |
| `hierarchical_context.py` 新增 `_has_colspan_rowspan(table)` | 护栏:无 colspan/rowspan 表走原逻辑,有的走展开。降低 G18a 等回归 |
| `tests/app/services/test_hierarchical_context.py` 新增基线 | TestTableToMarkdown(colspan/rowspan 展开)+ TestExtractAssemblySteps(mock HTML 断言 op5≥5) |

### 节点2:生成 content prompt 详实化(依赖节点1)
| 文件 | 改什么 |
|------|--------|
| `writing_agent.py:1551-1554` step_msg | "1-2句概括"→ 基于源 substeps 详实展开(保留 1.1/1.2 工步结构,100-200字)。强约束只用工步原文,不臆造 |
| `writing_agent.py:1569` max_tokens | 2500→3000 |
| `writing_agent.py:1560` 工步原文标注 | "要概括"→"按工步结构详实展开,保留全部工步信息" |

### 节点3:装配卡开头说明
| 文件 | 改什么 |
|------|--------|
| `hierarchical_context.py` 新增 `extract_assembly_overview(doc_dir)` | 独立方法(不动 extract_assembly_steps 契约),读 G25a 首页展开后 markdown 抽"说明"区 |
| `orchestrator.py:2630` 旁 + `writing_agent.py` G25a 分支 | 注入 assembly_overview 到生成 system_msg |

### 收尾
验证报告(extract op5 抽全 + content 100字+ + 回归)+ wiki + 清临时。

## 禁区
- **绝不臆造**:基于源 substeps 展开,triples 兜底,原文未提供→留空
- 不破坏无 colspan 表(护栏走原逻辑)
- 不破坏 extract_assembly_steps 契约(Dict[int,Dict]),overview 独立方法
- 不动 contract-align/content-quality 已落地
- 不碰其他章节单薄(后续 lead)

## 验证
- 节点1:op5 substeps 1→≥5/chars 9→≥150;op9 2/49→≥3/≥80;ASM_TOTAL 1134→≥1600;`'5.1.1' in text`=True;pytest 基线 + 全量数值对比不退化
- 节点2:diagnose_g25a content_avg 32→≥100;反验 op5 content 名词都在源 substeps
- 节点3:extract_assembly_overview 含"本工艺用于指导KZD..."
- 回归:pytest tests/ + G18a/G12a/G10a/G4a 列对齐

## ⚠️ 执行注意
- conda gywj;改 hierarchical_context 彻底重启(diagnose 直调无需)
- 节点1 前置 + 测试基线;colspan 回归护栏+测试+数值对比兜底
