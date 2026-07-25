# PLAN: 学习为画像 → 灌 craft KG（+文件夹批量 + SSE 进度）

> slug: `craft-kg-from-learn`（seal 后不可变）
> ALIGN: `ALIGN-craft-kg-from-learn.md`（已对齐，模糊点清零）
> 背景：修 `g25a-method-aux-bind` N1 规划漏洞（craft KG 壳做了无灌数据 → N3 空跑 → 装配卡辅料标准关联不工作）。

## Context

`g25a-method-aux-bind` 的 N1 做了全局 craft KG 的「壳」(`load_craft_kg`/`save_craft_kg`/全局实例 `craft_kg`/启动 `init_craft_kg`)，但 `save_craft_kg` **全库零调用、无灌数据链路** → `craft_kg` 永远空图 → N3 `_search_knowledge_graph` 被 `node_count>0` 守卫跳过(hierarchical_context.py:975)→ `aux_standards` 永远空 → N5 生成时辅料参数标准段不注入(writing_agent:1629 走空分支)。**N3 整层实际空跑**——这是 N1 规划漏洞，也是用户觉得「配套表↔工艺方法没关联」的根因之一。

用户定走 **A**：把「学习为画像」(learn 流程产 triples)→ `build_from_triples` → 合并进全局 `craft_kg` + save；按钮增强**文件夹批量**(后端新端点 + SSE 进度)。让 N3 有数据可查，相辅相成生成模型才真正生效。

## 已定决策（ALIGN 清零）

1. 数据源 = **triples**（`learn_from_content` 只产 triples 不产 graph；`build_from_triples` 现场建 KG 等价 graph 预存，够用）
2. 文件夹批量 = **后端新端点 + SSE 进度**（复用 localkb 自己的 SSE 模式）
3. domain 隔离**先不做**（看效果）
4. 重复 learn **累加幂等**
5. **单文件 learn 也灌 KG**（不只批量）

## 改动清单（4 节点，每节点 1 commit）

### N1: KG 合并方法 + 单文件 learn 灌 KG
| 文件 | 改什么 |
|---|---|
| `backend/app/services/knowledge_graph.py` | 加 `KnowledgeGraph.merge_from(other_kg)`：遍历 other 节点/边，`not in` 才 add（累加幂等；节点 ID 走 `_safe_id` :389 天然跨文件去重同名工序） |
| `backend/app/api/profile.py` | `learn_from_content` handler(:217-242)在 `learner.learn_from_content` 返回后加 helper `_feed_craft_kg(triples)`：`build_from_triples` → `craft_kg.merge_from` → `save_craft_kg`（全库首次接上） |

验证：点单文件「学习为画像」→ 后端日志 `craft_kg node_count > 0` + `data/knowledge_graph.json` 生成 + `python -c "from app.services.knowledge_graph import craft_kg, init_craft_kg; init_craft_kg(); print(craft_kg.node_count)"` 返回 > 0。

### N2: 后端批量端点 + SSE 进度
| 文件 | 改什么 |
|---|---|
| `backend/app/api/profile.py` | 新端点 `POST /{domain}/learn-batch`（吃 `file_ids: List[str]`，前端传该文件夹的文件 IDs）→ `StreamingResponse` async gen（复用 agent.py:524-543 模式）：遍历 file_ids → 按 id 读 content（复用现有按 id 读 content 路径）→ `learn_from_content` + `_feed_craft_kg` → yield `{type:progress, current, total, file}`；每个文件学完即 `save_craft_kg`（增量持久化，崩溃不丢）；末尾 yield `{type:complete, total}` |

验证：`curl -N -X POST learn-batch` → SSE 流推 progress/item_complete/complete → craft_kg.node_count 增长。

### N3: 前端文件夹批量按钮 + 进度 UI
| 文件 | 改什么 |
|---|---|
| `frontend/src/components/MaterialLibrary/FolderTree.tsx` | 文件夹右键菜单(:126-157 附近)加「批量学习为画像」→ `onLearnFolder` prop |
| `frontend/src/components/workspace/MaterialDrawer.tsx` | 加 `handleLearnFolder(folderId)`：取该 folder 下文件 IDs（复用 FileList.tsx:135 filteredFiles 逻辑）→ fetch learn-batch SSE（复用 useAIStream.ts:96 fetch stream 解析 `data:` 行）→ 复用现有 `processing`/`processingProgress`/`currentFile` 进度 UI(:523-560 Progress+Alert)显示 X/N |

验证：点文件夹按钮 → Progress 条实时 X/N + 当前文件名 → 完成提示。

### N4: 端到端冒烟 + pytest 回归
- pytest 回归（加 `merge_from` 单测 + `_feed_craft_kg` handler 单测）
- 端到端冒烟（**云端 LLM**）：点学习为画像 → KG 有数据 → 触发 G25a 生成 → N3 `aux_standards` 非空 → 工艺方法辅料一致性抽查

## 禁区
- 不改 `KnowledgeExtractor` 物料落库链路（C 全量自动灌入留后续）
- 不改 N3 `_search_knowledge_graph` 查询逻辑（craft_kg 有数据自动生效，无需改）
- 不动其他 source-driven 章节（G4a/G5a/G18a/G12a/G14a/G22a）
- 不做 domain 隔离 / 不一次性人工录大辅料参数库

## 复用的现有实现（不造新轮子）
- `KnowledgeGraph.build_from_triples`(knowledge_graph.py:239) + `_safe_id`(:389 跨文件去重)
- `craft_kg` 全局实例 + `save_craft_kg`(:423 / :436，首次接上)
- SSE 模式：`StreamingResponse(generate(), media_type="text/event-stream")` + `yield f"data: {json.dumps({'type':'progress',...})}\n\n"`(agent.py:524-543, 906)
- 前端 SSE 接收：fetch stream 解析 `data:` 行（useAIStream.ts:96-109）
- 前端进度 UI：`Progress` + `Alert`(MaterialDrawer.tsx:523-560 `processing` 模式)
- 文件夹概念：`FolderNode`(FolderTree.tsx:17-21) + `filteredFiles`(FileList.tsx:135)
- learn handler 已有的 Profile 持久化（`_save_profile`, profile.py）不动，只加灌 KG

## 验证（端到端）
1. **N1**：单文件学习为画像 → `data/knowledge_graph.json` 生成 + `init_craft_kg()` 后 `craft_kg.node_count > 0`。
2. **N2**：`curl -N POST /{domain}/learn-batch -d '{"file_ids":[...]}'` → SSE 流有 progress/complete。
3. **N3**：前端点文件夹「批量学习为画像」→ 进度条 X/N → `message.success`。
4. **N4**：pytest 回归 0 新 failed + 端到端（云端 LLM）：学习为画像灌 KG → 生成 G25a → 后端日志 `aux_standards` 非空 + 工艺方法辅料一致性抽查（周一内网 qwen3 再复验）。

## 后续（不在本期）
- C：extract 链路自动灌 KG（不依赖手动点学习为画像）
- domain 隔离（若召回跨专业串）
- triples 抽取规则覆盖度补（如「涂抹适量密封脂」的辅料）
