# PLAN: unify-selection-into-dialog（框选修改改 Cursor 式并入对话）

> slug: `unify-selection-into-dialog`（`dialog-task-pipeline` 延伸）。seal 后不可变。
> 原 PLAN `6141ac2` 按"quick-action 按钮"设计,用户改定 Cursor 式引用标签 + 删 quick_action,UI 全变,本文件重 seal 替换旧版。

## Context（为什么）
现状两套 AI 交互:①框选浮菜单(`AIContextMenu` 7 动作 → `useAIStream` → 旧端点 `/quick-actions-stream`)②对话(`AIChatPanel` → generate-stream)。用户要统一成 Cursor 式:删浮菜单,选中文字→浮一个"贴入"按钮→选区作为引用标签(小括号标注预览 + ×)贴到对话框上方→选区并入对话上下文让模型读。后端 `quick_action` 固定动作分支(造了但用户要的形态没它)一并删。

**技术核心决策**:`selected_text` 前端拼进 `user_input`(引用块前缀),**后端零改动**。理由(Plan agent 核实):意图识别只读 `user_input`(`intent_recognizer.py:205`)、`_dispatch_to_sub_agent` 签名无 context 形参(`orchestrator.py:668`)、generate 模式 shortcut 在 recognize 前短路不经 dispatch——独立字段方案送达不到 agent,要改主链签名(违反增量改)。前端拼装是唯一最小路径,且"选区+指令→edit 语义"正是 unify 想要的。

## 改动清单

### 前端
| 文件 | 改什么 |
|------|--------|
| `frontend/src/components/editor/AIContextMenu.tsx` + `.module.css` | **整文件删除**(7 动作浮菜单,不再用;已 grep 确认仅 MarkdownTiptapEditor:12 一处引用) |
| `frontend/src/components/common/MarkdownTiptapEditor.tsx` | 删 `import AIContextMenu`(:12)、`handleMenuClose`(:246);`AIContextMenu` 渲染段(:285-295)**替换为"贴入"浮按钮**(复用 `useSelection` 的 `position`/`isVisible`/`selection` 定位,点击 `onPasteToChat(selection.text)`;⚠ 实施时核实原 AIContextMenu 是否用 React portal,是则照搬避免被编辑器 overflow 裁切);Props 加 `onPasteToChat?: (text:string)=>void`;placeholder 文案改为"选中文字后点贴入送给 AI 助手"。`useSelection`(:157)保留 |
| `frontend/src/pages/WorkspacePage.tsx` | `MarkdownTiptapEditor`(:877-888)传 `onPasteToChat={(text)=>_setSelectedText(text)}`(新建选区→状态连接,当前断点);`AIChatPanel`(:932-938)传 `onClearSelectedText={()=>_setSelectedText('')}` |
| `frontend/src/components/AICreation/AIChatPanel.tsx` | Props 加 `onClearSelectedText?:()=>void`;删空 useEffect 占位(:139-143);:1404 审/校按钮行**前**插引用标签(`selectedText && <Tag closable onClose=onClearSelectedText>`,显示"📎 引用原文(N字):前40字...");`handleGenerate`(:445)加 `user_input` 拼装——`selectedText` 非空且非 generate/fill 模式时拼引用块前缀(`【用户引用的原文】<引用块开始>...<引用块结束>`),`selectedText` 有但 `inputText` 空时补默认指令"请针对我引用的原文进行处理";fetch 成功后调 `onClearSelectedText?.()`(贴入一次性) |

### 后端
| 文件 | 改什么 |
|------|--------|
| `backend/app/api/agent.py` | 删 quick_action 分支(:909-939,31 行,含 :914 动态 import ACTION_PROMPTS);删 `GenerateStreamRequest` 的 `quick_action`(:348)+`selected_text`(:349)字段(方案走 user_input,字段冗余) |

## 禁区(不动)
- generate/fill 主链(generation_mode shortcut → draft_complete → source-driven 零回归)
- `AISuggestionBar` 建议栏 + `useAIStream`(`MarkdownTiptapEditor:162-179`)+ `assistant.py` 旧端点 `/quick-actions-stream`(:632-694)+ ACTION_PROMPTS(:476-553)—— **AISuggestionBar 还在用,全保留**
- 审/校按钮(`AIChatPanel:1405-1422`)+ `/api/tasks/review|proofread`(保留作快捷入口)
- `intent_recognizer` / `_dispatch_to_sub_agent` / orchestrator(后端零改动)

## 验证
**端到端(手动,5 场景)**:
1. 编辑器选段→点"贴入"→对话框出引用标签(字数+预览)→输"帮我润色"→发送→后端日志确认 user_input 含引用块→AI 针对选区回复→标签发送后自动消失
2. 贴入后不输需求直接发→前端补默认指令,不报空
3. 点标签 × → 标签消失→发送 user_input 不含引用块
4. generate 模式贴入→发送→user_input **不含**引用块(守卫),生成正常
5. 贴 A→再贴 B→标签显示 B(覆盖不叠加)

**回归**:`AISuggestionBar` 流式正常 / generate / fill / 审校 / fallback QA / 后端 `python main.py` 无 import 错(grep `quick_action` 在 app/ 下除 assistant.py 外无残留) / `tsc 0 错` + `pytest`

## 风险
- 【中】意图识别漂移:选区拼进 user_input 进意图分类。缓解:引用块用醒目标记`【用户引用的原文】`+`<引用块>`,引导判 edit_document(选区+指令=编辑语义);严重时 v2 给 recognize 传剥离引用块的纯需求分类、拼装版生成
- 【中】浮按钮 portal:原 AIContextMenu 若 portal 到 body,新按钮须照搬,否则被 `MarkdownTiptapEditor:282` `position:relative` 容器裁切。实施时核实
- 【低】长选区:前端拼装 `selected_text[:2000]` 截断 + 标注,避 intent_recognizer `user_input[:500]` 截断丢分类
