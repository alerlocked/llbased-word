"""
Agent API路由
实现Agent对话、计划选择、素材确认等核心功能
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json
import asyncio

from app.shared.logging import get_logger
logger = get_logger(__name__)

router = APIRouter()


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


def get_system_prompt(mode: str) -> str:
    """根据模式返回系统提示词"""
    if mode == 'qa':
        return """你是一位专业的航天工艺文件知识助手。

## 核心原则：明确回答，不回避，不注水

每次回复必须让用户获得以下之一：
1. **明确答案** — 基于参考文档直接回答，引用来源（文档名+页码/表格号）
2. **明确方案** — 文档信息不足时，基于已有内容给出可行的补充方案，列出具体选项
3. **明确缺失提醒** — 告知用户哪些信息在当前素材库中确实不存在，建议上传哪些文档

绝对不要：
- 笼统说"参考文档中未提及"就结束 — 要指出缺什么、建议怎么补
- 用空话填充（"这是一个重要的问题"之类）
- 把检索到的原文简单复读 — 要提炼、结构化、指出适用范围和局限性

## 回答结构

### 信息充分时
直接给出答案，引用来源。简洁但不遗漏关键细节。

### 信息部分覆盖时
分两部分：
1. ✅ **已确认内容**（引用原文，注明来源）
2. ⚠️ **当前文档未覆盖的内容**（具体列出缺什么）

然后给出可行的补充方案。

### 信息完全缺失时
明确告知缺失，建议用户上传哪些标准或文档。

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
说明检索结果、素材状况、可靠性评估。

### ---EDITOR--- 区（写入编辑器）
只有以下情况才出现 ---EDITOR---：
- 素材充分，可以直接生成
- 用户明确要求生成（回复了确认/选择了方案）

不需要编辑器时（素材缺失等待确认、方向不明等待选择）不要加 ---EDITOR---。

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

    logger.info(f"[AI助手] 收到请求: prompt={user_input[:50]}..., session={session_id}, project={project_id}, materials={len(reference_materials)}")

    async def generate():
        try:
            logger.info(f"[AI助手] 开始处理请求")

            # 导入LLM服务
            from app.services.llm_service import llm_service
            from app.config import settings

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
            
            # 发送进度：正在分析
            yield f"data: {json.dumps({'type': 'progress', 'node': 'planner', 'message': '正在分析您的需求...'})}\n\n"

            logger.info(f"[AI助手] 调用LLM: model={settings.QWEN_TEXT_MODEL}")

            # 根据模式获取系统提示词
            system_prompt = get_system_prompt(mode)

            # 注入分层上下文（新增功能）
            doc_context = ""
            try:
                from app.services.hierarchical_context import hierarchical_context
                
                # 生成或使用现有 session_id
                current_session_id = session_id or "default"
                
                # 发送进度：正在加载上下文
                yield f"data: {json.dumps({'type': 'progress', 'node': 'context_loader', 'message': '正在加载工艺文档上下文...'})}\n\n"
                
                # 构建分层上下文（包含元信息查询优化）
                doc_context = hierarchical_context.build_context(
                    query=user_input,
                    session_id=current_session_id,
                    max_tokens=15000
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
                    material_instruction = "【系统提示】当前素材库中没有任何参考文档。请在回复中明确告知用户：请先通过素材库上传相关工艺文件。"
                elif material_status.get("missing_topics") and len(material_status["missing_topics"]) >= 2:
                    missing_str = "、".join(material_status["missing_topics"][:5])
                    doc_names = "、".join(d.get("name", "") for d in material_status.get("documents", []))
                    material_instruction = (
                        f"【素材状态】当前有参考文档（{doc_names}），"
                        f"但以下主题可能未被覆盖：{missing_str}。"
                        "基于已有素材回答，对缺少参考信息的部分明确告知用户。"
                    )

                logger.info(f"[AI助手] 上下文注入成功: 长度={len(doc_context)}, has_materials={material_status.get('has_documents')}")

            except Exception as e:
                logger.warning(f"[AI助手] 上下文注入失败（将继续无上下文生成）: {e}")
                # 上下文注入失败不影响主流程，继续生成
                doc_context = ""

            # Load domain profile and inject into context
            profile_context = ""
            try:
                domain = request.domain or "assembly"
                from app.models.profile import Profile
                from pathlib import Path
                profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"
                if profile_path.exists():
                    profile = Profile.from_json(profile_path)
                    profile_context = profile.to_context_text()
                    logger.info(f"[AI助手] 画像注入成功: domain={domain}, 长度={len(profile_context)}")
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
            if doc_context:
                context_parts.append(f"## 参考文档\n\n{doc_context}")
            if user_materials_context:
                context_parts.append(user_materials_context)

            if context_parts:
                user_message = "\n\n".join(context_parts) + f"\n\n## 用户问题\n\n{user_input}\n\n请基于参考文档和对话历史回答用户问题。如果参考文档中没有相关信息，请如实告知。"
            else:
                user_message = user_input

            messages.append({"role": "user", "content": user_message})

            # 发送进度：正在生成
            yield f"data: {json.dumps({'type': 'progress', 'node': 'writer', 'message': '正在生成回复...', 'data': {'content_preview': ''}})}\n\n"

            # 调用LLM生成内容 — 使用消息数组格式
            logger.info(f"[AI助手] 开始调用LLM API (messages={len(messages)})...")
            result = await llm_service.generate_with_messages(
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )

            if result.get("status") == "error":
                error_msg = result.get("error", "LLM调用失败")
                logger.error(f"[AI助手] LLM调用失败: {error_msg}")
                yield f"data: {json.dumps({'type': 'error', 'error': f'AI服务暂时不可用: {error_msg}'})}\n\n"
                return

            content = result.get("content", "")
            logger.info(f"[AI助手] LLM响应成功: 长度={len(content)}")

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

            # 发送最终结果
            if editor_content:
                # Has editor content: send chat part and editor part separately
                yield f"data: {json.dumps({'type': 'result', 'content': chat_content, 'has_editor': True, 'editor_content': editor_content}, ensure_ascii=False)}\n\n"
            else:
                # Pure chat response (no editor content)
                yield f"data: {json.dumps({'type': 'result', 'content': chat_content, 'has_editor': False}, ensure_ascii=False)}\n\n"

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
