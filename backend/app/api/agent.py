"""
Agent API路由
实现Agent对话、计划选择、素材确认等核心功能
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import uuid
import json
import asyncio

from app.shared.logging import get_logger
logger = get_logger(__name__)

router = APIRouter()


# ==================== 工艺文件标准框架 ====================

CRAFT_FILE_FRAMEWORK = """\
## 工艺文件标准框架（参考用，非强制填充）

| # | 模块 | 典型内容 |
|---|------|----------|
| 1 | 封面 | 文件名称、编号、产品代号、产品名称、编制/审核/批准签名+日期 |
| 2 | 工艺装备明细表 | 专用工艺装备清单：序号、名称、编号、数量 |
| 3 | 工具量具明细表 | 专用工具、量具清单 |
| 4 | 材料定额明细 | 主要材料 + 辅助材料（名称、牌号、规格、标准号、数量） |
| 5 | 引用文件目录 | 引用的标准、规范清单 |
| 6 | 装配件明细 | 零部组件代号、名称、数量、来源 |
| 7 | 工艺总方案 | 适用范围、人员要求、环境要求、装配前检查、通用注意事项 |
| 8 | 工序页 | 工序号→工序名称→工序内容→设备→工艺装备→工时定额 |
| 9 | 检测页 | 目视检测要求、检测参数、判定标准、记录要求 |
| 10 | 审签页 | 会签栏、编制/审核/批准签名栏 |
"""


def get_craft_system_prompt() -> str:
    """Get system prompt for craft file refinement mode (with uploaded file)."""
    return CRAFT_FILE_FRAMEWORK + """\

## 核心职责

你是工艺文件编辑助手。用户上传了一份工艺文件，你要在原有基础上改进它。

## 参考优先级（从高到低）

1. **上传文件本身** — 主要内容来源。尊重原文结构和已有数据，不随意删改。
2. **用户指令** — 用户说改哪里就改哪里，说润色就润色，说补某块就补某块。
3. **知识库** — 如果检索到相关参考文档，作为补充依据；没有也不强求。

## 工作原则

- **先读透再动笔**：综合三方面信息后一次性输出完整内容，不要边分析边输出碎片
- **以原文为底稿**：上传文件是已经写好的东西，大部分内容是完整的，只是写得不够好。你的任务是提升质量，不是重写
- **内容不空但需提升的常见情况**：
  - 工序描述过于简略，需要补充操作细节
  - 参数不完整（缺少公差、量具精度等）
  - 检测标准模糊，需要具体化
  - 表格数据有遗漏
- **标注规则**：基于推定的内容用 `[推定]` 标注，需要用户确认的内容用 `[待确认]` 标注

## 输出格式

### 分析区（对话气泡，150 字以内）
简要说明：原文整体状况、你要改什么、为什么改。不要长篇大论。

### ---EDITOR--- 区（写入编辑器）
改进后的完整工艺文件。用 Markdown 格式输出，保留原文的模块划分。表格用 Markdown table。

🚫 **禁止**使用 ---EDITOR--- 的情况：
- 尚未上传文件
- 正在等待用户确认方案

## 示例

用户上传了一份电缆装配工艺规程，说"帮我完善一下"。

> 📋 **分析**
> 原文结构完整（封面→材料→工序→检测），但工序页的参数描述偏简略，检测页缺少判定标准。我将基于原文补充工序细节和检测参数。
>
> ---
>
> ---EDITOR---
> （完整的改进后内容）
"""


# ==================== 模式检测 ====================

def detect_mode(user_input: str) -> str:
    """检测用户意图模式

    Returns:
        'qa' - 问答模式（询问信息）
        'write' - 写作模式（生成/修改/细化内容）
    """
    qa_keywords = ['多少', '是什么', '有没有', '在哪个', '哪些', '怎么', '为什么', '是否', '吗', '什么', '如何']
    write_keywords = [
        '写', '生成', '创建', '帮我', '修改', '优化', '完善', '帮我写', '生成一个',
        '细化', '展开', '补充', '扩展', '详细', '丰富', '润色', '重写', '改写',
        '续写', '续', ' elaborate', '细化一下', '展开写', '详细写',
    ]

    input_lower = user_input.lower()

    # 优先检测问答模式
    for keyword in qa_keywords:
        if keyword in input_lower:
            return 'qa'

    # 检测写作模式
    for keyword in write_keywords:
        if keyword in input_lower:
            return 'write'

    # 默认：短句（<20字）为问答，长句为写作
    return 'qa' if len(user_input) < 20 else 'write'


def _extract_graph_seeds(user_input: str, kg: Any) -> List[str]:
    """Extract node IDs from user input that match graph nodes.

    Matches user query terms against node labels using substring match.
    """
    seeds: List[str] = []
    for nid in kg._graph.nodes:
        node = kg._graph.nodes[nid]
        label = node.get("label", "")
        if label and label in user_input:
            seeds.append(nid)
    return seeds[:10]  # Limit seeds to avoid over-expansion


def get_system_prompt(mode: str) -> str:
    """根据模式返回系统提示词"""
    if mode == 'qa':
        return """你是一位专业的航天工艺文件知识助手。

## 核心原则：明确回答，不回避，不注水

每次回复必须让用户获得以下之一：
1. **明确答案** — 优先基于参考文档回答，引用来源；文档未覆盖时用通识知识补充回答，标注来源
2. **明确方案** — 文档信息不足时，基于已有内容+通识知识给出可行的补充方案
3. **诚实回答** — 文档没有、你也不知道的，直接说不知道，不要编造

## 长度约束
对话回复控制在 150 字以内。信息充分时直接给答案+来源，信息缺失时只列缺项+建议。

绝对不要：
- 笼统说"参考文档中未提及"就结束 — 要指出缺什么、建议怎么补
- 用空话填充（"这是一个重要的问题"之类）
- 把检索到的原文简单复读 — 要提炼、结构化、指出适用范围和局限性
- 使用 ---EDITOR--- 分隔符（QA 模式永远不写编辑器）

## 回答结构

### 信息充分时
直接给出答案，引用来源。简洁但不遗漏关键细节。

### 信息部分覆盖时
分两部分：
1. ✅ **已确认内容**（引用原文，注明来源）
2. 📖 **通识补充**（文档未覆盖但你了解的内容，标注「基于通识知识」）

如果通识知识也不足以回答，说"我暂时不了解这个问题的准确答案"。

### 信息完全缺失时
基于自身通识知识简短回答。回答开头加「本地知识库暂无相关内容，以下基于通识知识简答」，末尾建议用户上传相关文档。如果你也不知道，直接说不知道。

## 回答示例

用户：装配工艺卡片有多少页？
助手：根据文档信息，装配工艺卡片共有 15 页（来源：全单电缆装配规程.pdf）。

用户：目视检测有什么要求？
助手：根据《全单电缆装配规程.pdf》第18页，已确认的目视检测要求为：
1. 单发检视时间 ≥60s
2. 检视距离 25~30cm
3. 使用 ≥2W 强光手电辅助照明
4. 缺陷需记录并由相关方处理

⚠️ 当前文档未覆盖以下关键内容：
- 缺陷类型与分级判定标准
- 检测人员资质要求
- 环境照度参数（lux）
- 检测流程顺序与双人复核要求

建议上传《Q/Rp 1166-2024 机载导弹外观质量检查通用要求》以补充上述内容。
"""
    else:
        return """你是一位专业的航天工艺文件编辑助手。

## 核心职责

你是内容质量的把关者，也是用户需求的执行者。两者不矛盾：

1. **把关质量**：发现素材缺失时，必须先告知用户——缺什么、影响什么、可靠性如何。这是你的责任。
2. **执行需求**：用户了解情况后明确说了"先这样"、"用应急方案"、"生成"，那就按用户意思执行，不要再问。

简单说：**先报情况，让用户拿主意；用户拍板了，你就干活。**

## 工作流程

### 情况 A：素材充分
直接生成到编辑器，不需要额外确认。

### 情况 B：素材部分缺失
1. 先告诉用户缺什么、哪些内容不可靠
2. 提供方案让用户选择（比如：先出基础版 / 上传文档后再出完整版）
3. 等用户回复后，按用户选择执行
**不要自作主张直接生成推定内容**——用户可能更想先补齐素材。

### 情况 C：方向不明
给出 2-3 个具体方案让用户选，等用户回复。

### 情况 D：用户已经做了决定
用户说"先这样生成"、"用方案1"、"是"、"继续" → 直接执行，生成到编辑器，不要再确认。

## 输出格式

### 分析区（对话气泡显示）
说明检索结果、素材状况、可靠性评估。控制在 150 字以内，直接说结论和缺什么。

### ---EDITOR--- 区（写入编辑器）
只有以下情况才出现 ---EDITOR---：
- 素材充分，可以直接生成
- 用户明确要求生成（回复了确认/选择了方案）

🚫 以下情况**绝对禁止**使用 ---EDITOR---：
- 素材库中没有任何文档
- 素材部分缺失且用户尚未确认方案
- 正在等待用户选择或补充信息

不需要编辑器时不要加 ---EDITOR---，只返回纯对话内容。

推定内容用 `[推定]` 标注，待补充内容用 `[待补充]` 占位。

## 示例

#### 情况 B：素材缺失，先告知，等用户决定

> 📋 **分析**
> 根据《全单电缆装配规程.pdf》第18页，已有 4 项目视检测基本参数（时间/距离/照明/记录）。
>
> ⚠️ 以下内容在当前素材库中未找到原文：
> - 缺陷类型与分级判定标准
> - 检测人员资质要求
> - 检测流程顺序与复核机制
> - Q/Rp 1166-2024 被引用但未入库
>
> ---
>
> 💡 **方案**
> 1. **先出基础版** — 以 4 项已知参数为锚点，缺失项标注 [待补充]/[推定]，后续上传标准后迭代
> 2. **上传标准后再出** — 先上传 Q/Rp 1166-2024 和 2080.S2554，确保内容完整可靠
>
> 请选择（1/2）。

#### 情况 D：用户确认后，直接生成

（用户回复了"1"、"先出基础版"、"用应急方案"等）

> 📋 **分析**
> 基于现有 4 项参数生成基础版，缺失项标注 [推定]/[待补充]。
>
> ---
>
> ---EDITOR---
> ## 目视检测操作规范（基础版）
>
> ### 1. 检测前准备
> - 检测距离：25~30cm
> - 辅助照明：功率 ≥2W 强光手电
> - 单发检视时间：≥60s
>
> ### 2. 检测流程 [推定]
> - 按线束→连接器→固定点→走线路径顺序逐段检查
> - 每个连接器接口停留不少于 5s
>
> ### 3. 缺陷判定标准 [待补充]
> - 需 Q/Rp 1166-2024 原文补齐
>
> ### 4. 记录要求
> - 缺陷情况需记录，由相关方处理

#### 情况 A：素材充分，直接生成

> 📋 **分析**
> 根据《全单电缆装配规程.pdf》第16-18页，装配要求含完整的人员、量具、操作步骤信息，可直接生成。
>
> ---
>
> ---EDITOR---
> ## 装配要求
> ...
"""

# ==================== 请求/响应模型 ====================

class StartConversationRequest(BaseModel):
    """启动对话请求"""
    initial_input: str = Field(..., description="用户初始输入")
    reference_texts: List[str] = Field(default=[], description="参考文本列表")
    business_scenario: str = Field(default="general", description="业务场景")
    project_id: Optional[int] = Field(None, description="项目ID")
    user_id: int = Field(..., description="用户ID")


class ReplyQuestionRequest(BaseModel):
    """回复问题请求"""
    session_id: str = Field(..., description="会话ID")
    question_id: str = Field(..., description="问题ID")
    answer: str = Field(..., description="用户回答")
    selected_option_id: Optional[str] = Field(None, description="选择的选项ID")


class SelectPlanRequest(BaseModel):
    """选择计划请求"""
    session_id: str = Field(..., description="会话ID")
    plan_option_id: str = Field(..., description="计划选项ID")
    custom_plan: Optional[str] = Field(None, description="自定义计划")


class ConfirmMaterialsRequest(BaseModel):
    """确认素材请求"""
    session_id: str = Field(..., description="会话ID")
    selected_material_ids: List[str] = Field(default=[], description="选中的素材ID")
    excluded_material_ids: List[str] = Field(default=[], description="排除的素材ID")
    additional_keywords: List[str] = Field(default=[], description="额外关键词")


class ApplySuggestionsRequest(BaseModel):
    """应用建议请求"""
    session_id: str = Field(..., description="会话ID")
    applied_suggestions: List[str] = Field(default=[], description="应用的建议ID")
    rejected_suggestions: List[str] = Field(default=[], description="拒绝的建议ID")
    custom_changes: Optional[str] = Field(None, description="自定义修改")


class ChatRequest(BaseModel):
    """聊天请求"""
    content: str = Field(..., description="聊天内容")
    session_id: Optional[str] = Field(None, description="会话ID")


class GenerateStreamRequest(BaseModel):
    """流式生成请求"""
    session_id: Optional[str] = Field(None, description="会话ID")
    content: Optional[str] = Field(None, description="生成内容描述")
    user_input: Optional[str] = Field(None, description="用户输入（兼容旧版）")
    user_id: Optional[int] = Field(None, description="用户ID")
    project_id: Optional[int] = Field(None, description="项目ID")
    domain: Optional[str] = Field(None, description="工艺类型 (assembly/welding/coating/general)")
    reference_materials: Optional[List[dict]] = Field(None, description="用户选中的参考素材")
    chat_history: Optional[List[dict]] = Field(None, description="最近对话历史 [{role, content}]")
    uploaded_file_content: Optional[str] = Field(None, description="临时上传文件解析后的纯文本内容")
    uploaded_file_name: Optional[str] = Field(None, description="临时上传文件名")


class SelectSolutionRequest(BaseModel):
    """选择方案请求"""
    session_id: str = Field(..., description="会话ID")
    solution_id: str = Field(..., description="方案ID")


class GenerateArticleRequest(BaseModel):
    """生成文章请求"""
    project_id: int = Field(..., description="项目ID")
    article_type: str = Field(default="general", description="文章类型")
    style_id: Optional[int] = Field(None, description="风格ID")


# ==================== 会话存储 ====================

# 内存中存储会话状态（生产环境应使用Redis）
sessions: Dict[str, Dict[str, Any]] = {}


def create_session(user_id: int) -> str:
    """创建新会话"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "user_id": user_id,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "questions": [],
        "materials": [],
        "plans": [],
        "suggestions": [],
        "todos": [],
        "current_step": "initialized"
    }
    return session_id


# ==================== API端点 ====================

@router.post("/start-conversation")
async def start_conversation(request: StartConversationRequest):
    """
    启动Agent对话

    基于用户输入启动一个新的Agent会话
    """
    logger.info(f"🚀 启动Agent对话: user_id={request.user_id}, scenario={request.business_scenario}")

    try:
        # 创建会话
        session_id = create_session(request.user_id)
        session = sessions[session_id]

        # 保存初始输入
        session["initial_input"] = request.initial_input
        session["reference_texts"] = request.reference_texts
        session["business_scenario"] = request.business_scenario
        session["project_id"] = request.project_id

        # 生成初始问题（模拟Agent分析后的结果）
        questions = [
            {
                "id": f"q_{uuid.uuid4().hex[:8]}",
                "question": "您希望生成的工艺文件类型是什么？",
                "question_type": "goal",
                "options": [
                    {"id": "opt1", "text": "工艺卡片", "description": "标准工艺流程卡片"},
                    {"id": "opt2", "text": "作业指导书", "description": "详细操作步骤文档"},
                    {"id": "opt3", "text": "检验规范", "description": "质量检验标准文档"},
                    {"id": "opt4", "text": "技术协议", "description": "技术要求协议文档"}
                ],
                "allow_custom": True
            }
        ]
        session["questions"] = questions
        session["current_step"] = "collecting_info"

        logger.info(f"✅ 会话创建成功: session_id={session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "status": "collecting_info",
            "message": "会话已启动，请回答以下问题",
            "questions": questions,
            "todos": [
                {"id": "todo1", "title": "确认文件类型", "status": "in_progress"},
                {"id": "todo2", "title": "收集素材信息", "status": "pending"},
                {"id": "todo3", "title": "生成初稿", "status": "pending"}
            ]
        }

    except Exception as e:
        logger.error(f"❌ 启动对话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动对话失败: {str(e)}"
        )


@router.post("/reply-question")
async def reply_question(request: ReplyQuestionRequest):
    """
    回复Agent问题

    用户回答Agent提出的问题
    """
    logger.info(f"📝 回复问题: session={request.session_id}, question={request.question_id}")

    try:
        session = sessions.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 记录回答
        if "answers" not in session:
            session["answers"] = []
        session["answers"].append({
            "question_id": request.question_id,
            "answer": request.answer,
            "selected_option_id": request.selected_option_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # 根据回答生成下一个问题或进入下一阶段
        remaining_questions = [q for q in session["questions"]
                             if q["id"] != request.question_id and
                             not any(a["question_id"] == q["id"] for a in session.get("answers", []))]

        if remaining_questions:
            return {
                "success": True,
                "status": "collecting_info",
                "message": "回答已记录",
                "next_question": remaining_questions[0]
            }
        else:
            # 所有问题已回答，进入素材收集阶段
            session["current_step"] = "collecting_materials"
            return {
                "success": True,
                "status": "materials_ready",
                "message": "信息收集完成，准备素材分析",
                "material_report": {
                    "materials": [
                        {
                            "id": f"mat_{i}",
                            "title": f"参考素材 {i+1}",
                            "content": "从项目文档中提取的相关内容...",
                            "source": "project",
                            "material_type": "document",
                            "value_description": "包含工艺参数和流程信息",
                            "priority": "high" if i == 0 else "medium"
                        }
                        for i in range(3)
                    ],
                    "recommendations": ["mat_0", "mat_1"],
                    "summary": "已从项目文档中提取3个相关素材"
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 回复问题失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回复问题失败: {str(e)}"
        )


@router.post("/reply-question-stream")
async def reply_question_stream(request: ReplyQuestionRequest):
    """
    流式回复问题

    以SSE方式返回Agent响应
    """
    logger.info(f"🌊 流式回复问题: session={request.session_id}")

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'})}\n\n"

        # 调用同步方法处理
        try:
            result = await reply_question(request)
            yield f"data: {json.dumps({'type': 'complete', 'data': result})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/select-plan")
async def select_plan(request: SelectPlanRequest):
    """
    选择生成计划

    用户选择或自定义生成计划
    """
    logger.info(f"📋 选择计划: session={request.session_id}, plan={request.plan_option_id}")

    try:
        session = sessions.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 记录选择的计划
        session["selected_plan"] = {
            "plan_id": request.plan_option_id,
            "custom_plan": request.custom_plan,
            "selected_at": datetime.utcnow().isoformat()
        }
        session["current_step"] = "plan_selected"

        return {
            "success": True,
            "status": "plan_selected",
            "message": "计划已选择，准备开始生成",
            "plan": {
                "id": request.plan_option_id,
                "name": "标准工艺文件生成",
                "steps": [
                    "分析参考素材",
                    "提取关键工艺参数",
                    "生成工艺流程",
                    "添加检验要求",
                    "格式化输出"
                ]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 选择计划失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"选择计划失败: {str(e)}"
        )


@router.get("/material-report/{session_id}")
async def get_material_report(session_id: str):
    """
    获取素材报告

    返回Agent分析后的素材推荐报告
    """
    logger.info(f"📊 获取素材报告: session={session_id}")

    try:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        return {
            "success": True,
            "material_report": {
                "materials": session.get("materials", [
                    {
                        "id": f"mat_{i}",
                        "title": f"参考素材 {i+1}",
                        "content": "从项目文档中提取的相关内容...",
                        "source": "project",
                        "material_type": "document",
                        "value_description": "包含工艺参数和流程信息",
                        "priority": "high" if i == 0 else "medium",
                        "relevance_score": 0.95 if i == 0 else 0.75
                    }
                    for i in range(3)
                ]),
                "recommendations": ["mat_0"],
                "priority_ranking": ["mat_0", "mat_1", "mat_2"],
                "summary": "已从项目文档中提取3个相关素材，建议使用前2个"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取素材报告失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取素材报告失败: {str(e)}"
        )


@router.post("/confirm-materials")
async def confirm_materials(request: ConfirmMaterialsRequest):
    """
    确认素材

    用户确认要使用的素材
    """
    logger.info(f"✅ 确认素材: session={request.session_id}, selected={len(request.selected_material_ids)}")

    try:
        session = sessions.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 记录确认的素材
        session["confirmed_materials"] = {
            "selected_ids": request.selected_material_ids,
            "excluded_ids": request.excluded_material_ids,
            "additional_keywords": request.additional_keywords,
            "confirmed_at": datetime.utcnow().isoformat()
        }
        session["current_step"] = "materials_confirmed"

        return {
            "success": True,
            "status": "materials_confirmed",
            "message": f"已确认{len(request.selected_material_ids)}个素材",
            "next_step": "review_suggestions"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 确认素材失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认素材失败: {str(e)}"
        )


@router.get("/review-suggestions/{session_id}")
async def get_review_suggestions(session_id: str):
    """
    获取审核建议

    返回Agent生成的内容审核建议
    """
    logger.info(f"💡 获取审核建议: session={session_id}")

    try:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        return {
            "success": True,
            "suggestions": [
                {
                    "id": "sug_1",
                    "title": "建议添加工艺参数",
                    "description": "当前内容缺少具体的工艺参数，建议补充加工参数",
                    "priority": "high",
                    "location": "第2段落"
                },
                {
                    "id": "sug_2",
                    "title": "完善检验要求",
                    "description": "建议添加具体的检验标准和验收要求",
                    "priority": "medium",
                    "location": "检验章节"
                }
            ],
            "improvement_plans": [
                {
                    "id": "plan_a",
                    "name": "方案A",
                    "title": "完整版",
                    "suggestions": [
                        {"id": "s1", "title": "添加工艺参数", "priority": "high"},
                        {"id": "s2", "title": "完善检验要求", "priority": "medium"}
                    ],
                    "recommended": True
                },
                {
                    "id": "plan_b",
                    "name": "方案B",
                    "title": "精简版",
                    "suggestions": [
                        {"id": "s1", "title": "添加关键参数", "priority": "high"}
                    ],
                    "recommended": False
                }
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取审核建议失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取审核建议失败: {str(e)}"
        )


@router.post("/apply-suggestions")
async def apply_suggestions(request: ApplySuggestionsRequest):
    """
    应用建议

    应用用户选择的改进建议
    """
    logger.info(f"🔧 应用建议: session={request.session_id}")

    try:
        session = sessions.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 记录应用的建议
        session["applied_suggestions"] = {
            "applied": request.applied_suggestions,
            "rejected": request.rejected_suggestions,
            "custom_changes": request.custom_changes,
            "applied_at": datetime.utcnow().isoformat()
        }
        session["current_step"] = "ready_to_generate"

        return {
            "success": True,
            "status": "suggestions_applied",
            "message": f"已应用{len(request.applied_suggestions)}个建议",
            "next_step": "generate"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 应用建议失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"应用建议失败: {str(e)}"
        )


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    与Agent聊天

    简单的对话接口
    """
    logger.info(f"💬 聊天: session={request.session_id}")

    try:
        # 如果没有session_id，创建新会话
        if not request.session_id:
            session_id = create_session(user_id=1)
        else:
            session_id = request.session_id
            if session_id not in sessions:
                session_id = create_session(user_id=1)

        session = sessions[session_id]

        # 记录对话
        if "messages" not in session:
            session["messages"] = []
        session["messages"].append({
            "role": "user",
            "content": request.content,
            "timestamp": datetime.utcnow().isoformat()
        })

        # 生成响应（实际应调用LLM）
        response_text = f"收到您的消息：{request.content[:50]}... 我已理解您的需求，请继续描述您想要的工艺文件内容。"

        session["messages"].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "success": True,
            "session_id": session_id,
            "response": response_text
        }

    except Exception as e:
        logger.error(f"❌ 聊天失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"聊天失败: {str(e)}"
        )


async def _generate_via_orchestrator(
    user_input: str,
    uploaded_file_content: str,
    uploaded_file_name: str,
    session_id: Optional[str],
    reference_materials: list,
    project_id: Optional[int],
) -> AsyncGenerator[str, None]:
    """Route uploaded-file requests through ProcessOrchestrator.

    Flow: plan → auto-confirm → WritingAgent execute → stream result
    Yields SSE events compatible with the existing frontend AIChatPanel.
    """
    from app.agents.orchestrator.orchestrator import ProcessOrchestrator

    yield f"data: {json.dumps({'type': 'mode', 'mode': 'write'})}\n\n"
    yield f"data: {json.dumps({'type': 'progress', 'message': '正在分析上传文件...'})}\n\n"

    orchestrator = ProcessOrchestrator()
    context = {
        "uploaded_file_content": uploaded_file_content,
        "uploaded_file_name": uploaded_file_name,
        "has_uploaded_file": True,
        "project_id": project_id,
        "reference_materials": reference_materials,
    }

    try:
        result = await orchestrator.process_intent(
            user_input=user_input,
            context=context,
            task_name=f"补齐-{uploaded_file_name}",
        )

        if not result.get("success"):
            error_msg = result.get("error", "处理失败")
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return

        # Case A: plan generated, awaiting confirmation → auto-confirm and execute
        if result.get("requires_response") and result.get("interaction_type") == "draft_plan_review":
            plan = result.get("modification_plan", "")
            yield f"data: {json.dumps({'type': 'progress', 'message': '方案已生成，正在执行修改...'})}\n\n"

            # Show the plan in the chat bubble
            yield f"data: {json.dumps({'type': 'content', 'content': f'📋 **修改方案**\n\n{plan[:500]}...\n\n正在执行修改...'})}\n\n"

            # Auto-confirm and execute
            from app.agents.orchestrator.interaction_models import UserResponse, InputType

            confirm_response = UserResponse(
                input_type=InputType.TEXT,
                content="确认执行",
                selected_option="confirm",
            )
            exec_result = await orchestrator.continue_conversation(
                task_id=result.get("task_id") or orchestrator.current_task_id,
                user_response=confirm_response,
            )

            if exec_result.get("success"):
                # Extract the generated content
                agent_result = exec_result.get("result", {})
                inner = agent_result.get("result", {})
                if isinstance(inner, dict):
                    new_content = inner.get("content") or inner.get("result", {}).get("content", "")
                else:
                    new_content = str(inner)

                if new_content:
                    # Send analysis summary in chat bubble
                    yield f"data: {json.dumps({'type': 'content', 'content': '✅ 工艺文件已按框架完善，内容已输出到编辑器。'})}\n\n"
                    # Send the full content to editor via ---EDITOR---
                    editor_content = f"---EDITOR---\n{new_content}\n---END EDITOR---"
                    yield f"data: {json.dumps({'type': 'content', 'content': editor_content})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'content', 'content': '执行完成但未生成内容。'})}\n\n"
            else:
                error_msg = exec_result.get("error", "执行失败")
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"

        # Case B: direct result (no confirmation needed)
        else:
            generated = result.get("result", {}).get("generated_content", "")
            if not generated:
                generated = result.get("message", "处理完成")
            yield f"data: {json.dumps({'type': 'content', 'content': generated})}\n\n"

    except Exception as e:
        logger.error(f"[AI助手] Orchestrator error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': f'Agent处理异常: {str(e)}'})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/generate-stream")
async def generate_stream(request: GenerateStreamRequest):
    """
    流式生成内容

    以SSE方式流式返回生成的内容
    调用真正的LLM服务进行内容生成
    """
    # 获取用户输入（支持多种字段名）
    user_input = request.content or request.user_input or ""
    session_id = request.session_id
    project_id = request.project_id
    user_id = request.user_id or 1
    reference_materials = request.reference_materials or []
    uploaded_file_content = request.uploaded_file_content
    uploaded_file_name = request.uploaded_file_name

    logger.info(f"[AI助手] 收到请求: prompt={user_input[:50]}..., session={session_id}, project={project_id}, materials={len(reference_materials)}, uploaded_file={'yes' if uploaded_file_content else 'no'}")

    async def generate():
        try:
            logger.info(f"[AI助手] 开始处理请求")

            # 导入LLM服务
            from app.services.llm_service import llm_service
            from app.config import settings

            # ── Agent routing: uploaded file → Orchestrator ──
            if uploaded_file_content:
                async for event in _generate_via_orchestrator(
                    user_input=user_input,
                    uploaded_file_content=uploaded_file_content,
                    uploaded_file_name=uploaded_file_name or "uploaded_file",
                    session_id=session_id,
                    reference_materials=reference_materials,
                    project_id=project_id,
                ):
                    yield event
                return
            # ── Default: direct LLM stream ──

            # 检查API配置
            if not settings.DASHSCOPE_API_KEY:
                logger.error("[AI助手] DASHSCOPE_API_KEY 未配置")
                yield f"data: {json.dumps({'type': 'error', 'error': 'API密钥未配置，请联系管理员配置DASHSCOPE_API_KEY'})}\n\n"
                return

            # 检测模式（问答 vs 写作）
            mode = detect_mode(user_input)
            logger.info(f"[AI助手] 模式检测: mode={mode}, input={user_input[:30]}...")
            
            # 发送模式消息
            yield f"data: {json.dumps({'type': 'mode', 'mode': mode})}\n\n"
            
            # 发送进度：思考中
            yield f"data: {json.dumps({'type': 'progress', 'message': '思考中...'})}\n\n"

            logger.info(f"[AI助手] 调用LLM: model={settings.QWEN_TEXT_MODEL}")

            # 根据模式获取系统提示词
            # If a temp file is uploaded, use craft file framework prompt
            if uploaded_file_content:
                system_prompt = get_craft_system_prompt()
                # Force write mode for file-based interactions
                mode = 'write'
                logger.info("[AI助手] 检测到临时上传文件，切换到工艺文件框架模式")
            else:
                system_prompt = get_system_prompt(mode)

            # 注入分层上下文（新增功能）
            doc_context = ""
            try:
                from app.services.hierarchical_context import hierarchical_context

                # 生成或使用现有 session_id
                current_session_id = session_id or "default"

                # Context loading progress (no separate step displayed to user)
                logger.info("[AI助手] 正在加载工艺文档上下文...")

                # Build layered context with mode-aware loading strategy
                # When a file is uploaded, enrich the query with file name keywords
                # so Layer 3 can find matching knowledge base documents
                context_query = user_input
                if uploaded_file_content:
                    file_keywords = uploaded_file_name or ""
                    # Also extract key identifiers from the file content (first 500 chars)
                    content_head = uploaded_file_content[:500] if uploaded_file_content else ""
                    context_query = f"{user_input} {file_keywords} {content_head}"
                    logger.info(f"[AI助手] 上下文搜索 query 已拼接上传文件信息: {context_query[:100]}...")

                doc_context = hierarchical_context.build_context(
                    query=context_query,
                    session_id=current_session_id,
                    max_tokens=15000,
                    mode=mode,  # qa=light, write=full, review=structure-only
                )

                # When a file is uploaded (craft file mode), do multi-pass retrieval.
                # A single query only returns ~4000 tokens of fragments.
                # For "complete this document" tasks we need targeted per-module searches
                # so the LLM gets real data instead of fabricating content.
                if uploaded_file_content:
                    # Craft file module names for targeted search
                    module_queries = [
                        "工艺装备明细表 专用装备",
                        "工具量具明细表 专用工具 量具",
                        "材料定额明细 主要材料 辅助材料",
                        "引用文件目录 标准 规范",
                        "装配件明细 零部组件",
                        "工艺总方案 适用范围 人员 环境",
                        "工序 装配工艺卡 工序内容",
                        "检测 目视 检验 绝缘",
                    ]
                    extra_parts: list[str] = []
                    seen_snippets: set[str] = set()

                    for mq in module_queries:
                        results = hierarchical_context.global_keyword_search(
                            query=mq, top_k=3
                        )
                        for r in results:
                            snippet = r.get("snippet", "")
                            doc_name = r.get("doc_name", "")
                            page = r.get("page", "?")
                            score = r.get("score", 0)
                            # Deduplicate by snippet content
                            dedup_key = snippet[:80]
                            if dedup_key in seen_snippets or score < 2:
                                continue
                            seen_snippets.add(dedup_key)
                            extra_parts.append(
                                f"- **{doc_name}** (第{page}页, 相关度:{score}): {snippet}"
                            )

                    if extra_parts:
                        extra_section = (
                            "## 补充检索结果（按模块分类）\n\n"
                            + "\n".join(extra_parts)
                        )
                        doc_context += f"\n\n{extra_section}"
                        logger.info(
                            f"[AI助手] 多轮补充检索: {len(extra_parts)} 个片段, "
                            f"总上下文 {len(doc_context)} chars"
                        )

                # 尝试元信息快速查询
                meta_answer = hierarchical_context.search_meta_info(user_input)
                if meta_answer:
                    logger.info(f"[AI助手] 元信息查询命中: {meta_answer}")
                    # 元信息查询成功，在上下文前面添加快速回答
                    doc_context = f"# 快速参考\n\n{meta_answer}\n\n---\n\n{doc_context}"

                # Get material status and build instruction
                material_status = hierarchical_context.get_material_status(user_input)
                material_instruction = ""
                if not material_status.get("has_documents"):
                    material_instruction = (
                        "【系统提示】当前素材库为空。"
                        "回答规则：优先从本地知识库检索，如未找到相关信息，可基于自身通识知识简短回答。"
                        "回答开头必须加一句：「本地知识库暂无相关内容，以下基于通识知识简答」。"
                        "回答末尾建议用户上传相关工艺文档以获取更准确的指导。"
                    )
                elif material_status.get("missing_topics") and len(material_status["missing_topics"]) >= 2:
                    missing_str = "、".join(material_status["missing_topics"][:5])
                    doc_names = "、".join(d.get("name", "") for d in material_status.get("documents", []))
                    material_instruction = (
                        f"【素材状态】当前有参考文档（{doc_names}），"
                        f"但以下主题可能未被覆盖：{missing_str}。"
                        "回答规则：先基于参考文档回答已覆盖的部分，对未覆盖的部分用自身通识知识补充回答，"
                        "并标注「该部分基于通识知识，非当前文档内容」。"
                        "如果你也不知道答案，直接说不知道，不要编造。"
                    )

                logger.info(f"[AI助手] 上下文注入成功: 长度={len(doc_context)}, has_materials={material_status.get('has_documents')}")

            except Exception as e:
                logger.warning(f"[AI助手] 上下文注入失败（将继续无上下文生成）: {e}")
                # 上下文注入失败不影响主流程，继续生成
                doc_context = ""

            # Load domain profile and inject into context
            profile_context = ""
            graph_context = ""
            loaded_profile = None
            try:
                domain = request.domain or "assembly"
                from app.models.profile import Profile
                from pathlib import Path
                profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"
                if profile_path.exists():
                    loaded_profile = Profile.from_json(profile_path)
                    profile_context = loaded_profile.to_context_text()
                    logger.info(f"[AI助手] 画像注入成功: domain={domain}, 长度={len(profile_context)}")

                    # Graph-based context expansion for query-relevant knowledge
                    if loaded_profile.graph and loaded_profile.graph.get("nodes"):
                        from app.services.knowledge_graph import KnowledgeGraph
                        kg = KnowledgeGraph.from_dict(loaded_profile.graph)
                        # Extract potential node IDs from user query
                        seed_ids = _extract_graph_seeds(user_input, kg)
                        if seed_ids:
                            graph_context = kg.to_context_text(seed_ids, max_tokens=400)
                            if graph_context:
                                logger.info(f"[AI助手] 图上下文扩展命中: seeds={seed_ids}, 长度={len(graph_context)}")
            except Exception as e:
                logger.warning(f"[AI助手] 画像加载失败: {e}")
                profile_context = ""

            # 构建完整提示词
            # 构建用户选中的素材上下文
            user_materials_context = ""
            if reference_materials:
                user_materials_context = "\n\n## 用户选中的参考素材\n\n" + "\n\n".join([
                    f"### 【{m.get('name', '未命名素材')}】\n{m.get('content', '')}"
                    for m in reference_materials
                ])
                logger.info(f"[AI助手] 注入用户选中素材: {len(reference_materials)} 个")

            # Inject material instruction if available
            material_instruction = locals().get('material_instruction', '')
            material_section = f"\n{material_instruction}\n" if material_instruction else ""

            # Determine conversation phase for context injection
            if not material_status.get("has_documents"):
                conversation_phase = (
                    "【当前阶段：通识问答】素材库为空。"
                    "优先从本地知识库检索，如未找到相关信息，可基于通识知识简短回答。"
                    "回答开头加「本地知识库暂无相关内容，以下基于通识知识简答」，末尾建议上传相关文档。\n"
                    "绝对禁止使用 ---EDITOR---（因为没有参考文档）。"
                )
            elif material_status.get("missing_topics") and len(material_status.get("missing_topics", [])) >= 2:
                conversation_phase = "【当前阶段：素材评估】部分素材缺失。先在对话中告知用户缺什么，等用户确认后再使用 ---EDITOR---。"
            else:
                conversation_phase = "【当前阶段：内容生成】素材充足，可以基于参考文档直接生成内容。"
            material_section += f"\n{conversation_phase}\n"

            # Build structured message array (OpenAI/Claude standard format)
            # instead of flattening everything into one string.
            # This lets the model natively distinguish system rules, prior turns,
            # retrieved context, and the current user input.

            messages: List[Dict[str, str]] = []

            # 1. System message: behavior rules + profile
            system_parts = [system_prompt]
            if material_section:
                system_parts.append(material_section)
            if profile_context:
                system_parts.append(f"\n## 当前用户画像\n{profile_context}")
            messages.append({"role": "system", "content": "\n".join(system_parts)})

            # 2. Chat history (prior turns from current session)
            chat_history = request.chat_history or []
            for msg in chat_history[-10:]:  # Keep last 10 turns
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if not content:
                    continue
                # Map frontend roles to API roles
                api_role = "assistant" if role == "assistant" else "user"
                # Truncate very long messages
                if len(content) > 500:
                    content = content[:500] + "..."
                messages.append({"role": api_role, "content": content})

            # 3. Current user message with injected context
            # Context (retrieved docs + materials) goes with the current user message
            # so the model knows these are reference materials for THIS query
            context_parts: List[str] = []
            if uploaded_file_content:
                file_label = uploaded_file_name or "上传文件"
                context_parts.append(f"## 用户上传的文件：{file_label}\n\n{uploaded_file_content}")
                logger.info(f"[AI助手] 注入上传文件内容: {len(uploaded_file_content)} chars")
            if doc_context:
                context_parts.append(f"## 参考文档\n\n{doc_context}")
            if graph_context:
                context_parts.append(f"## 相关工艺知识关系\n\n{graph_context}")
            if user_materials_context:
                context_parts.append(user_materials_context)

            if context_parts:
                user_message = "\n\n".join(context_parts) + f"\n\n## 用户问题\n\n{user_input}\n\n请基于参考文档和对话历史回答用户问题。如果参考文档中没有相关信息，请如实告知。"
            else:
                user_message = user_input

            messages.append({"role": "user", "content": user_message})

            # Sending progress (kept minimal for frontend spinner)
            yield f"data: {json.dumps({'type': 'progress', 'message': '正在生成回复...'})}\n\n"

            # Route to model tier by mode: QA→simple(fast), write→complex(capable)
            model_tier = "simple" if mode == "qa" else "complex"
            # Use higher token limit for craft file framework mode
            max_gen_tokens = 4000 if uploaded_file_content else 2000
            logger.info(f"[AI助手] 调用LLM(流式): tier={model_tier}, messages={len(messages)}, max_tokens={max_gen_tokens}")

            # --- Streaming LLM call ---
            full_content = ""
            full_thinking = ""
            async for chunk in llm_service.generate_with_messages_stream(
                messages=messages,
                temperature=0.7,
                max_tokens=max_gen_tokens,
                tier=model_tier,
            ):
                chunk_type = chunk.get("type", "")
                chunk_content = chunk.get("content", "")

                if chunk_type == "thinking":
                    full_thinking += chunk_content
                    yield f"data: {json.dumps({'type': 'thinking', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                elif chunk_type == "content":
                    full_content += chunk_content
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                elif chunk_type == "error":
                    logger.error(f"[AI助手] 流式LLM错误: {chunk_content}")
                    yield f"data: {json.dumps({'type': 'error', 'error': f'AI服务暂时不可用: {chunk_content}'})}\n\n"
                    return

            content = full_content
            logger.info(f"[AI助手] LLM响应成功(流式): 长度={len(content)}")

            # Parse EDITOR separator: split chat content from editor content
            EDITOR_MARKER = "---EDITOR---"
            chat_content = content
            editor_content = ""

            if EDITOR_MARKER in content:
                parts = content.split(EDITOR_MARKER, 1)
                chat_content = parts[0].strip()
                editor_content = parts[1].strip() if len(parts) > 1 else ""

            # Async save conversation memory (fire-and-forget)
            try:
                from app.services.hierarchical_context import hierarchical_context
                hierarchical_context._memory_service.save_summary_async(
                    session_id, user_input, content
                )
            except Exception as mem_err:
                logger.warning(f"[AI助手] 记忆保存跳过: {mem_err}")

            # Send final result — only editor info, not content (already streamed)
            if editor_content:
                yield f"data: {json.dumps({'type': 'result', 'has_editor': True, 'editor_content': editor_content}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"

            logger.info(f"[AI助手] 流式输出完成")

        except Exception as e:
            logger.error(f"[AI助手] 处理异常: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': f'处理失败: {str(e)}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/select-solution")
async def select_solution(request: SelectSolutionRequest):
    """
    选择方案

    用户从多个方案中选择一个
    """
    logger.info(f"✅ 选择方案: session={request.session_id}, solution={request.solution_id}")

    try:
        session = sessions.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 记录选择的方案
        session["selected_solution"] = request.solution_id
        session["current_step"] = "solution_selected"

        return {
            "success": True,
            "status": "solution_selected",
            "message": "方案已选择",
            "solution_id": request.solution_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 选择方案失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"选择方案失败: {str(e)}"
        )


@router.post("/generate-article")
async def generate_article(request: GenerateArticleRequest):
    """
    生成文章

    基于项目生成工艺文件
    """
    logger.info(f"📄 生成文章: project={request.project_id}, type={request.article_type}")

    try:
        # 创建新会话
        session_id = create_session(user_id=1)
        session = sessions[session_id]
        session["project_id"] = request.project_id
        session["article_type"] = request.article_type
        session["style_id"] = request.style_id

        return {
            "success": True,
            "session_id": session_id,
            "status": "generating",
            "message": "文章生成已开始",
            "task_id": f"task_{uuid.uuid4().hex[:8]}"
        }

    except Exception as e:
        logger.error(f"❌ 生成文章失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成文章失败: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务状态

    查询异步任务的状态
    """
    logger.info(f"📊 获取任务状态: task={task_id}")

    return {
        "success": True,
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "任务已完成",
        "result": {
            "title": "生成的工艺文件",
            "content": "# 工艺文件\n\n## 概述\n\n本文件描述了标准工艺流程..."
        }
    }


@router.post("/todos/{session_id}/{todo_id}/complete")
async def complete_todo(session_id: str, todo_id: str):
    """
    标记待办完成

    标记某个待办事项为已完成
    """
    logger.info(f"✅ 完成待办: session={session_id}, todo={todo_id}")

    try:
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        # 更新待办状态
        for todo in session.get("todos", []):
            if todo.get("id") == todo_id:
                todo["status"] = "completed"
                todo["completed_at"] = datetime.utcnow().isoformat()

        return {
            "success": True,
            "message": "待办已标记为完成",
            "todo_id": todo_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 完成待办失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"完成待办失败: {str(e)}"
        )
