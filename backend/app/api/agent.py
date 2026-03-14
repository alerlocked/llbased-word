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

from app.utils.logger import logger

router = APIRouter()

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
    session_id: str = Field(..., description="会话ID")
    content: str = Field(..., description="生成内容描述")


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
    """
    logger.info(f"🌊 流式生成: session={request.session_id}")

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'message': '开始生成...'})}\n\n"

        # 模拟流式生成
        content_parts = [
            "# 工艺文件\n\n",
            "## 1. 概述\n\n",
            "本工艺文件描述了...",
            "\n\n## 2. 工艺流程\n\n",
            "1. 准备工作\n",
            "2. 加工操作\n",
            "3. 检验验收\n",
            "\n\n## 3. 参数要求\n\n",
            "- 加工温度: 常温\n",
            "- 加工精度: ±0.1mm\n",
            "\n\n[生成完成]"
        ]

        for part in content_parts:
            await asyncio.sleep(0.1)  # 模拟延迟
            yield f"data: {json.dumps({'type': 'content', 'content': part})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'message': '生成完成'})}\n\n"

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
