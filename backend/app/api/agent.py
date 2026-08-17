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
    generation_mode: Optional[str] = Field(None, description="生成模式: 'generate' 全部生成, 'fill' 补齐缺失章节")


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
    流式生成内容 — ALL requests go through ProcessOrchestrator

    Flow: user input → orchestrator.process_intent() → SSE events
    - draft_complete: plan → confirm → execute via WritingAgent
    - other intents: context build → LLM streaming (with orchestrator context)
    """
    # 获取用户输入（支持多种字段名）
    user_input = request.content or request.user_input or ""
    session_id = request.session_id
    project_id = request.project_id
    user_id = request.user_id or 1
    reference_materials = request.reference_materials or []
    uploaded_file_content = request.uploaded_file_content
    uploaded_file_name = request.uploaded_file_name
    generation_mode = request.generation_mode

    logger.info(
        f"[AI助手] 收到请求: prompt={user_input[:50]}..., session={session_id}, "
        f"project={project_id}, materials={len(reference_materials)}, "
        f"uploaded_file={'yes' if uploaded_file_content else 'no'}"
    )

    async def generate():
        try:
            from app.services.llm_service import llm_service
            from app.config import settings
            from app.agents.orchestrator.orchestrator import ProcessOrchestrator

            # 检查API配置
            if not settings.DASHSCOPE_API_KEY:
                logger.error("[AI助手] DASHSCOPE_API_KEY 未配置")
                yield f"data: {json.dumps({'type': 'error', 'error': 'API密钥未配置，请联系管理员配置DASHSCOPE_API_KEY'})}\n\n"
                return

            # ── Fast-fail: probe LLM reachability before entering generation ──
            # Sync urllib probe wrapped in to_thread to avoid blocking the event loop.
            import asyncio as _asyncio
            reachable, reason = await _asyncio.to_thread(llm_service.check_llm_reachable)
            if not reachable:
                logger.error(f"[AI助手] LLM 不可达,快速失败: {reason}")
                yield f"data: {json.dumps({'type': 'error', 'error': f'模型服务不可达:{reason}。请检查 .env 内网地址(DASHSCOPE_BASE_URL_COMPLEX)及模型服务状态。'}, ensure_ascii=False)}\n\n"
                return

            # ── Mode detection (for frontend UI hints) ──
            mode = detect_mode(user_input)
            if uploaded_file_content:
                mode = 'write'
            logger.info(f"[AI助手] 模式检测: mode={mode}, input={user_input[:30]}...")

            yield f"data: {json.dumps({'type': 'mode', 'mode': mode})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'message': '正在加载知识库...'})}\n\n"

            # ── Build context for orchestrator ──
            orch_context = _build_orchestrator_context(
                request=request,
                user_input=user_input,
                mode=mode,
            )

            # ── Route through ProcessOrchestrator ──
            yield f"data: {json.dumps({'type': 'progress', 'message': '正在分析意图...'})}\n\n"
            orchestrator = ProcessOrchestrator()
            logger.info(f"[AI助手] 调用 ProcessOrchestrator.process_intent()")

            orch_result = await orchestrator.process_intent(
                user_input=user_input,
                context=orch_context,
                task_name=f"AI助手请求-{session_id or 'anon'}",
            )

            intent_type = orch_result.get("intent", {}).get("type", "unknown")
            logger.info(
                f"[AI助手] Orchestrator 完成: success={orch_result.get('success')}, "
                f"intent={intent_type}, state={orch_result.get('state')}"
            )

            # ── Handle orchestrator result → SSE events ──
            if not orch_result.get("success"):
                error_msg = orch_result.get("error", "主控处理失败")
                logger.error(f"[AI助手] Orchestrator error: {error_msg}")
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
                return

            # Case 0a: gated draft_complete (dialog tried to trigger generate/fill)
            if orch_result.get("state") == "gated":
                yield f"data: {json.dumps({'type': 'content', 'content': orch_result.get('message', '')}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"
                _persist_turn(
                    session_id, request.project_id, user_input,
                    content=orch_result.get("message", ""), intent_type="gated_draft_complete",
                )
                return

            # Case 0b: review_document → four-way factual review (chat-only,
            # never touches the editor). Falls back to state outputs.generated
            # snapshot when no in-session structured results exist.
            if intent_type == "review_document":
                try:
                    from app.services.review_pipeline import run_review
                    from app.services.project_state_service import project_state_service

                    project_state = (
                        project_state_service.load(request.project_id)
                        if request.project_id else {}
                    )
                    review = await run_review(
                        user_input=user_input,
                        project_state=project_state,
                        structured_results=None,  # cross-session: snapshot path
                    )
                    yield f"data: {json.dumps({'type': 'progress', 'message': '已完成四对照审查（模板/数据库/内容质量/需求）'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': review['reply']}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"
                    logger.info(
                        "[AI助手] review_pipeline 完成",
                        issues=len(review.get("issues", [])),
                    )
                    _persist_turn(
                        session_id, request.project_id, user_input,
                        content=review["reply"], intent_type="review_document",
                    )
                except Exception as e:
                    logger.error(f"[AI助手] review_pipeline 失败: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'error': f'审查执行失败: {e}'}, ensure_ascii=False)}\n\n"
                return

            # Case 0c: edit_document → safe fallback until the dialog-edit
            # workflow (colleague line) lands. Never rewrites the document.
            if intent_type == "edit_document" and not request.generation_mode:
                fallback = (
                    "已识别为修改需求。修改功能建设中（正由协作线开发），"
                    "当前请使用编辑器框选或生成按钮操作——我不会从对话直接改文件。"
                )
                yield f"data: {json.dumps({'type': 'content', 'content': fallback}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"
                _persist_turn(
                    session_id, request.project_id, user_input,
                    content=fallback, intent_type="edit_document_fallback",
                )
                return

            # Case 1: draft_complete → show analysis then auto-confirm and execute
            if orch_result.get("requires_response"):
                plan = orch_result.get("modification_plan", "")
                missing_chapters = orch_result.get("missing_chapters", [])

                # Show material status as progress (separate visual indicator)
                material_status = orch_result.get("material_status", {})
                if material_status:
                    doc_count = material_status.get("document_count", 0)
                    missing = material_status.get("missing_topics", [])
                    if not material_status.get("has_documents"):
                        if missing_chapters:
                            mat_msg = "素材状态：未选择额外参考素材，将使用知识库已解析文档生成"
                        else:
                            mat_msg = "素材状态：未选择参考素材，知识库也无可用文档"
                    elif missing and len(missing) >= 2:
                        mat_msg = f"素材状态：{doc_count} 个文档，部分覆盖（可能缺失：{'、'.join(missing[:3])}）"
                    else:
                        mat_msg = f"素材状态：充足（{doc_count} 个文档）"
                    yield f"data: {json.dumps({'type': 'progress', 'message': mat_msg}, ensure_ascii=False)}\n\n"

                # Build structured analysis report as chat content
                analysis_lines = ["**初稿分析报告**", ""]
                if missing_chapters:
                    analysis_lines.append(
                        f"与知识库文档对比后，发现初稿缺失以下 {len(missing_chapters)} 个章节："
                    )
                    for i, ch in enumerate(missing_chapters, 1):
                        if isinstance(ch, dict):
                            title = ch.get("title", "")
                            reason = ch.get("reason", "")
                            analysis_lines.append(f"{i}. {title}（{reason}）" if reason else f"{i}. {title}")
                        else:
                            analysis_lines.append(f"{i}. {ch}")
                    # Material status note
                    if material_status and material_status.get("has_documents"):
                        analysis_lines.append("")
                        analysis_lines.append(f"当前知识库有 {material_status.get('document_count', 0)} 个参考文档，可直接用于生成。无需补充新材料。")
                    elif material_status and not material_status.get("has_documents"):
                        analysis_lines.append("")
                        if missing_chapters:
                            analysis_lines.append(f"未选择额外参考素材，将基于知识库已解析文档生成 {len(missing_chapters)} 个章节。")
                        else:
                            analysis_lines.append("⚠ 知识库暂无可用文档，生成内容可能不够准确。建议先上传相关标准文档到素材库。")
                    # Implementation plan
                    analysis_lines.append("")
                    analysis_lines.append(f"**实施计划**：将逐章从知识库原文中提取对应内容，并行生成 {len(missing_chapters)} 个缺失章节，确保参数、代号、材料名称与原文一致。")
                else:
                    analysis_lines.append("初稿章节基本完整，将进行内容优化。")

                yield f"data: {json.dumps({'type': 'content', 'content': chr(10).join(analysis_lines)}, ensure_ascii=False)}\n\n"
                logger.info(f"[draft_complete] 分析报告已发送, missing_chapters={len(missing_chapters)}")

                # Signal a new message section before execution starts
                yield f"data: {json.dumps({'type': 'content_section'}, ensure_ascii=False)}\n\n"

                # Show execution progress
                if missing_chapters:
                    exec_msg = f"正在按章节提取原文并生成内容（{len(missing_chapters)} 个章节并行）..."
                else:
                    exec_msg = "正在执行修改方案..."
                yield f"data: {json.dumps({'type': 'progress', 'message': exec_msg}, ensure_ascii=False)}\n\n"
                logger.info(f"[draft_complete] 进度消息已发送: {exec_msg}")

                # Auto-confirm: tell orchestrator to execute the plan
                from app.agents.orchestrator.interaction_models import UserResponse, InputType

                confirm_response = UserResponse(
                    session_id=session_id or "default",
                    response_type=InputType.TEXT,
                    content="确认执行",
                    selected_option="confirm",
                )
                logger.info("[draft_complete] 开始自动确认，调用 continue_conversation")
                exec_result = await orchestrator.continue_conversation(
                    user_response=confirm_response,
                )
                logger.info(f"[draft_complete] continue_conversation 返回: success={exec_result.get('success')}, keys={list(exec_result.keys())}")

                if exec_result.get("success"):
                    # Extract generated content from _execute_draft_modification result
                    result_wrapper = exec_result.get("result", {})
                    agent_result = result_wrapper.get("agent_result", {})
                    modules_generated = result_wrapper.get("modules_generated", 0)
                    structured_results = result_wrapper.get("structured_results", {})
                    logger.info(f"[draft_complete] result_wrapper keys={list(result_wrapper.keys()) if isinstance(result_wrapper, dict) else 'not-dict'}")
                    logger.info(f"[draft_complete] agent_result type={type(agent_result).__name__}, keys={list(agent_result.keys()) if isinstance(agent_result, dict) else 'not-dict'}")
                    new_content = ""
                    if isinstance(agent_result, dict):
                        inner = agent_result.get("result", {})
                        logger.info(f"[draft_complete] inner type={type(inner).__name__}, keys={list(inner.keys()) if isinstance(inner, dict) else str(inner)[:100]}")
                        if isinstance(inner, dict):
                            new_content = inner.get("content") or inner.get("result", {}).get("content", "")
                            logger.info(f"[draft_complete] 提取到 new_content 长度={len(new_content)}")

                    # Template-first: if structured_results exist, emit template output
                    # even when new_content (Markdown) is empty
                    if not new_content and structured_results and isinstance(structured_results, dict) and len(structured_results) > 0:
                        # Per-chapter row-gap warnings (G25a per-row completeness)
                        # — surfaced BEFORE content/result so they are visible
                        # even if the client navigates away on result.
                        for _code, _data in structured_results.items():
                            if not isinstance(_data, dict):
                                continue
                            for _w in (_data.get("warnings") or []):
                                _warn_msg = f"[{_code}] {_w.get('message', '')}"
                                yield f"data: {json.dumps({'type': 'warning', 'message': _warn_msg}, ensure_ascii=False)}\n\n"
                        from app.services.template_types import StructuredDocument, ChapterData

                        try:
                            from app.services.template_loader import load_template
                            template = load_template("assembly_process_cable")
                            tmpl_name = template.get("template_name", "")

                            chapters = []
                            for code, data in structured_results.items():
                                if isinstance(data, dict):
                                    chapters.append(ChapterData(
                                        chapter_code=code,
                                        chapter_title=data.get("chapter_title", ""),
                                        table_type=data.get("table_type", ""),
                                        filled_data=data.get("filled_data", []),
                                        left_data=data.get("left_data"),
                                        right_data=data.get("right_data"),
                                        flow_steps=data.get("flow_steps"),
                                        field_values=data.get("field_values"),
                                        fill_sources=data.get("fill_sources"),
                                    ))

                            doc = StructuredDocument(
                                template_id="assembly_process_cable",
                                template_name=tmpl_name,
                                chapters=chapters,
                            )
                            template_json = doc.to_dict()

                            summary = (
                                "工艺文件表格已生成。\n\n"
                                f"共生成 {len(chapters)} 个章节的结构化表格数据，"
                                "请在编辑器中查看和编辑。"
                            )
                            yield f"data: {json.dumps({'type': 'content', 'content': summary}, ensure_ascii=False)}\n\n"
                            sse_result = {
                                'type': 'result',
                                'has_editor': True,
                                'editor_content': '',
                                'content_format': 'template',
                                'template_data': template_json,
                            }
                            yield f"data: {json.dumps(sse_result, ensure_ascii=False)}\n\n"
                            logger.info(f"[draft_complete] template output: {len(chapters)} chapters (no markdown)")
                            _output_summary = {
                                "chapters": [
                                    {
                                        "code": code,
                                        "title": (data.get("chapter_title", "") if isinstance(data, dict) else ""),
                                        "rows": len(data.get("filled_data") or []) if isinstance(data, dict) else 0,
                                    }
                                    for code, data in (structured_results or {}).items()
                                    if isinstance(data, dict)
                                ],
                                "warnings_count": sum(
                                    len((d.get("warnings") or []))
                                    for d in (structured_results or {}).values()
                                    if isinstance(d, dict)
                                ),
                            }
                            _persist_turn(
                                session_id, request.project_id, user_input,
                                content=json.dumps(template_json, ensure_ascii=False),
                                intent_type=intent_type,
                                focus_chapters=list(structured_results.keys()) if isinstance(structured_results, dict) else None,
                                output_summary=_output_summary,
                            )
                        except Exception as e:
                            logger.warning(f"[draft_complete] template assembly failed (no-markdown path): {e}")
                            yield f"data: {json.dumps({'type': 'content', 'content': '执行完成但模板组装失败。'}, ensure_ascii=False)}\n\n"
                            yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"

                    elif new_content:
                        # Build completion summary with chapter info
                        if missing_chapters:
                            summary = (
                                "修改方案已执行完成。\n\n"
                                f"基于知识库原文补充了 {len(missing_chapters)} 个缺失章节，"
                                f"生成内容 {len(new_content)} 字已输出到编辑器。\n\n"
                                f"补充章节：{'、'.join(ch.get('title', str(ch)) if isinstance(ch, dict) else str(ch) for ch in missing_chapters)}"
                            )
                        elif modules_generated > 0:
                            summary = (
                                "修改方案已执行完成。\n\n"
                                f"共补充 {modules_generated} 个缺失模块，"
                                f"生成内容 {len(new_content)} 字已输出到编辑器。"
                            )
                        else:
                            summary = f"内容生成完成，共 {len(new_content)} 字已输出到编辑器。"
                        yield f"data: {json.dumps({'type': 'content', 'content': summary}, ensure_ascii=False)}\n\n"
                        # Send generated content to editor
                        logger.info(f"[draft_complete] 发送 editor_content SSE: 长度={len(new_content)}")

                        # Check if template-driven generation produced structured results
                        if structured_results and isinstance(structured_results, dict) and len(structured_results) > 0:
                            from app.services.template_types import StructuredDocument
                            from app.services.content_assembler import assemble_from_template

                            # Try to load template for structured assembly
                            try:
                                from app.services.template_loader import load_template
                                template = load_template("assembly_process_cable")
                                tmpl_name = template.get("template_name", "")

                                # Build StructuredDocument from results
                                from app.services.template_types import ChapterData
                                chapters = []
                                for code, data in structured_results.items():
                                    logger.info("template_assemble_chapter", code=code,
                                                filled=len(data.get("filled_data", [])) if isinstance(data, dict) else -1,
                                                data_keys=list(data.keys()) if isinstance(data, dict) else [])
                                    if isinstance(data, dict):
                                        chapters.append(ChapterData(
                                            chapter_code=code,
                                            chapter_title=data.get("chapter_title", ""),
                                            table_type=data.get("table_type", ""),
                                            filled_data=data.get("filled_data", []),
                                            left_data=data.get("left_data"),
                                            right_data=data.get("right_data"),
                                            flow_steps=data.get("flow_steps"),
                                            field_values=data.get("field_values"),
                                            fill_sources=data.get("fill_sources"),
                                        ))

                                doc = StructuredDocument(
                                    template_id="assembly_process_cable",
                                    template_name=tmpl_name,
                                    chapters=chapters,
                                )
                                template_json = doc.to_dict()
                                logger.info(f"[draft_complete] template structured: {len(chapters)} chapters")
                            except Exception as e:
                                logger.warning(f"[draft_complete] template assembly failed: {e}")
                                template_json = None

                            sse_result = {
                                'type': 'result',
                                'has_editor': True,
                                'editor_content': new_content,
                                'content_format': 'template',
                                'template_data': template_json,
                            }
                        else:
                            sse_result = {
                                'type': 'result',
                                'has_editor': True,
                                'editor_content': new_content,
                                'content_format': 'markdown',
                            }
                        yield f"data: {json.dumps(sse_result, ensure_ascii=False)}\n\n"
                        _persist_turn(
                            session_id, request.project_id, user_input,
                            content=new_content, intent_type=intent_type,
                            focus_chapters=list(structured_results.keys()) if isinstance(structured_results, dict) and structured_results else None,
                            output_summary=(
                                {
                                    "chapters": [
                                        {"code": c, "title": (d.get("chapter_title", "") if isinstance(d, dict) else ""), "rows": len(d.get("filled_data") or []) if isinstance(d, dict) else 0}
                                        for c, d in structured_results.items() if isinstance(d, dict)
                                    ],
                                    "warnings_count": sum(len((d.get("warnings") or [])) for d in structured_results.values() if isinstance(d, dict)),
                                }
                                if isinstance(structured_results, dict) and structured_results else None
                            ),
                        )
                    else:
                        logger.warning(f"[draft_complete] new_content 为空! agent_result={str(agent_result)[:200]}")
                        yield f"data: {json.dumps({'type': 'content', 'content': '执行完成但未生成内容。'}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"
                else:
                    error_msg = exec_result.get("error", "执行失败")
                    logger.error(f"[draft_complete] exec_result success=False: {error_msg}")
                    yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"

                logger.info("[AI助手] draft_complete auto-confirm 执行完成")
                return

            # Case 2: Orchestrator produced content via sub-agents
            agg_result = orch_result.get("result", {})
            generated_content = ""

            # Try to extract content from aggregated result
            if isinstance(agg_result, dict):
                generated_content = agg_result.get("generated_content", "")
                # Also check component results
                if not generated_content and agg_result.get("components"):
                    for comp in agg_result["components"]:
                        if comp.get("status") == "completed" and comp.get("result"):
                            comp_result = comp["result"]
                            if isinstance(comp_result, dict):
                                inner = comp_result.get("result", {})
                                if isinstance(inner, dict):
                                    generated_content += inner.get("content", "")

            if generated_content:
                # Orchestrator produced content — send as SSE
                logger.info(f"[AI助手] Orchestrator 产出内容: {len(generated_content)} chars")

                # Parse EDITOR separator
                EDITOR_MARKER = "---EDITOR---"
                chat_content = generated_content
                editor_content = ""

                if EDITOR_MARKER in generated_content:
                    parts = generated_content.split(EDITOR_MARKER, 1)
                    chat_content = parts[0].strip()
                    editor_content = parts[1].strip() if len(parts) > 1 else ""

                # Send chat content
                if chat_content:
                    yield f"data: {json.dumps({'type': 'content', 'content': chat_content}, ensure_ascii=False)}\n\n"

                # Save memory + roll project state
                _persist_turn(
                    session_id, request.project_id, user_input,
                    content=generated_content, intent_type=intent_type,
                )

                # Send final result
                if editor_content:
                    yield f"data: {json.dumps({'type': 'result', 'has_editor': True, 'editor_content': editor_content}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"

                logger.info("[AI助手] Orchestrator 内容输出完成")
                return

            # Case 3: Orchestrator produced no content (e.g. QA, unknown intent)
            # Fall back to streaming LLM with orchestrator-built context
            logger.info("[AI助手] Orchestrator 无直接内容，fallback 到流式 LLM")

            yield f"data: {json.dumps({'type': 'progress', 'message': '正在生成回复...'})}\n\n"

            system_prompt = get_craft_system_prompt() if uploaded_file_content else get_system_prompt(mode)
            messages = _build_llm_messages(
                system_prompt=system_prompt,
                user_input=user_input,
                doc_context=orch_context.get("doc_context", ""),
                profile_context=orch_context.get("profile_context", ""),
                graph_context=orch_context.get("graph_context", ""),
                material_section=orch_context.get("material_section", ""),
                uploaded_file_content=uploaded_file_content,
                uploaded_file_name=uploaded_file_name,
                reference_materials=reference_materials,
                chat_history=request.chat_history or [],
                project_state_block=orch_context.get("project_state_block", ""),
            )

            model_tier = "simple" if mode == "qa" else "complex"
            max_gen_tokens = 4000 if uploaded_file_content else 2000
            logger.info(f"[AI助手] Fallback LLM(流式): tier={model_tier}, messages={len(messages)}")

            # Streaming LLM call
            full_content = ""
            async for chunk in llm_service.generate_with_messages_stream(
                messages=messages,
                temperature=0.7,
                max_tokens=max_gen_tokens,
                tier=model_tier,
            ):
                chunk_type = chunk.get("type", "")
                chunk_content = chunk.get("content", "")

                if chunk_type == "thinking":
                    yield f"data: {json.dumps({'type': 'thinking', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                elif chunk_type == "content":
                    full_content += chunk_content
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                elif chunk_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'error': f'AI服务暂时不可用: {chunk_content}'})}\n\n"
                    return

            # Parse EDITOR separator
            EDITOR_MARKER = "---EDITOR---"
            chat_content = full_content
            editor_content = ""
            if EDITOR_MARKER in full_content:
                parts = full_content.split(EDITOR_MARKER, 1)
                chat_content = parts[0].strip()
                editor_content = parts[1].strip() if len(parts) > 1 else ""

            # Save memory + roll project state (fallback streaming path uses mode as intent)
            _persist_turn(
                session_id, request.project_id, user_input,
                content=full_content, intent_type=mode,
            )

            # Send final result
            if editor_content:
                yield f"data: {json.dumps({'type': 'result', 'has_editor': True, 'editor_content': editor_content}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'result', 'has_editor': False}, ensure_ascii=False)}\n\n"

            logger.info("[AI助手] 流式输出完成")

        except Exception as e:
            logger.error(f"[AI助手] 处理异常: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': f'处理失败: {str(e)}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _build_orchestrator_context(
    request: GenerateStreamRequest,
    user_input: str,
    mode: str,
) -> Dict[str, Any]:
    """Build context dict for ProcessOrchestrator.

    Loads: hierarchical context, domain profile, material status,
    uploaded file, reference materials.
    """
    from app.config import settings

    ctx: Dict[str, Any] = {
        "session_id": request.session_id or "default",
        "user_id": request.user_id or 1,
        "project_id": request.project_id,
        "domain": request.domain or "assembly",
        "has_uploaded_file": bool(request.uploaded_file_content),
        "uploaded_file_content": request.uploaded_file_content,
        "uploaded_file_name": request.uploaded_file_name,
        "mode": mode,
        "generation_mode": request.generation_mode,
    }

    # ── Hierarchical context ──
    doc_context = ""
    material_status: Dict[str, Any] = {}
    try:
        from app.services.hierarchical_context import hierarchical_context

        current_session_id = request.session_id or "default"
        context_query = user_input
        if request.uploaded_file_content:
            file_keywords = request.uploaded_file_name or ""
            content_head = request.uploaded_file_content[:500]
            context_query = f"{user_input} {file_keywords} {content_head}"
            logger.info(f"[AI助手] 上下文搜索 query 已拼接上传文件信息: {context_query[:100]}...")

        doc_context = hierarchical_context.build_context(
            query=context_query,
            session_id=current_session_id,
            max_tokens=15000,
            mode=mode,
            project_id=request.project_id,
        )

        # Multi-pass retrieval for craft file mode
        if request.uploaded_file_content:
            doc_context = _multi_pass_retrieval(hierarchical_context, doc_context)

        # Meta info quick query
        meta_answer = hierarchical_context.search_meta_info(user_input)
        if meta_answer:
            logger.info(f"[AI助手] 元信息查询命中: {meta_answer}")
            doc_context = f"# 快速参考\n\n{meta_answer}\n\n---\n\n{doc_context}"

        # Material status
        material_status = hierarchical_context.get_material_status(user_input)

        logger.info(
            f"[AI助手] 上下文注入成功: 长度={len(doc_context)}, "
            f"has_materials={material_status.get('has_documents')}"
        )
    except Exception as e:
        logger.warning(f"[AI助手] 上下文注入失败（将继续无上下文生成）: {e}")

    ctx["doc_context"] = doc_context
    ctx["material_status"] = material_status

    # ── Domain profile ──
    profile_context = ""
    graph_context = ""
    try:
        from app.models.profile import Profile
        from pathlib import Path
        domain = request.domain or "assembly"
        profile_path = Path(settings.DATA_DIR) / "profiles" / f"{domain}.json"
        if profile_path.exists():
            loaded_profile = Profile.from_json(profile_path)
            profile_context = loaded_profile.to_context_text()
            logger.info(f"[AI助手] 画像注入成功: domain={domain}, 长度={len(profile_context)}")

            # KnowledgeGraph expansion removed (service deleted in cleanup);
            # graph kept as plain dict on Profile, rendered in to_context_text().
            # graph_context stays empty here; reintroduce in Step F if needed.
    except Exception as e:
        logger.warning(f"[AI助手] 画像加载失败: {e}")

    ctx["profile_context"] = profile_context
    ctx["graph_context"] = graph_context

    # ── Project working state (session continuity) ──
    project_state_block = ""
    if request.project_id:
        try:
            from app.services.project_state_service import project_state_service

            project_state_block = project_state_service.render_context_block(
                project_state_service.load(request.project_id)
            )
            if project_state_block:
                logger.info(
                    f"[AI助手] 项目工作状态注入成功: project_id={request.project_id}, 长度={len(project_state_block)}"
                )
        except Exception as e:
            logger.warning(f"[AI助手] 项目工作状态加载失败（将继续无状态生成）: {e}")

    ctx["project_state_block"] = project_state_block

    # ── Material status instruction ──
    # Retrieval-empty: library has docs but L3 keyword search hit nothing for this query.
    retrieval_empty = bool(
        material_status.get("has_documents")
        and not getattr(hierarchical_context, "_last_l3_hit", True)
    )
    material_instruction = ""
    if retrieval_empty:
        material_instruction = (
            "【检索结果】本地知识库有文档，但本次提问未检索到相关内容。"
            "回答规则：必须明确告知「本地知识库未检索到相关内容」；"
            "如需补充可基于通识知识简短回答并标注「以下基于通识知识，非文档内容」；"
            "禁止编造文档中不存在的内容。"
        )
    elif not material_status.get("has_documents"):
        material_instruction = (
            "【系统提示】当前素材库为空。"
            "回答规则：优先从本地知识库检索，如未找到相关信息，可基于自身通识知识简短回答。"
            "回答开头必须加一句：「本地知识库暂无相关内容，以下基于通识知识简答」。"
            "回答末尾建议用户上传相关工艺文档以获取更准确的指导。"
        )
    elif material_status.get("missing_topics") and len(material_status.get("missing_topics", [])) >= 2:
        missing_str = "、".join(material_status["missing_topics"][:5])
        doc_names = "、".join(d.get("name", "") for d in material_status.get("documents", []))
        material_instruction = (
            f"【素材状态】当前有参考文档（{doc_names}），"
            f"但以下主题可能未被覆盖：{missing_str}。"
            "回答规则：先基于参考文档回答已覆盖的部分，对未覆盖的部分用自身通识知识补充回答，"
            "并标注「该部分基于通识知识，非当前文档内容」。"
            "如果你也不知道答案，直接说不知道，不要编造。"
        )

    # Conversation phase
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

    material_section = f"\n{material_instruction}\n" if material_instruction else ""
    material_section += f"\n{conversation_phase}\n"
    ctx["material_section"] = material_section

    return ctx


def _multi_pass_retrieval(hierarchical_context: Any, base_context: str) -> str:
    """Run targeted per-module searches for craft file completion tasks."""
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
        results = hierarchical_context.global_keyword_search(query=mq, top_k=3)
        for r in results:
            snippet = r.get("snippet", "")
            doc_name = r.get("doc_name", "")
            page = r.get("page", "?")
            score = r.get("score", 0)
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
        base_context += f"\n\n{extra_section}"
        logger.info(f"[AI助手] 多轮补充检索: {len(extra_parts)} 个片段, 总上下文 {len(base_context)} chars")

    return base_context


def _build_llm_messages(
    system_prompt: str,
    user_input: str,
    doc_context: str = "",
    profile_context: str = "",
    graph_context: str = "",
    material_section: str = "",
    uploaded_file_content: Optional[str] = None,
    uploaded_file_name: Optional[str] = None,
    reference_materials: Optional[List[dict]] = None,
    chat_history: Optional[List[dict]] = None,
    project_state_block: str = "",
) -> List[Dict[str, str]]:
    """Build structured message array for LLM call."""
    messages: List[Dict[str, str]] = []

    # 1. System message
    system_parts = [system_prompt]
    if material_section:
        system_parts.append(material_section)
    if profile_context:
        system_parts.append(f"\n## 当前用户画像\n{profile_context}")
    if project_state_block:
        system_parts.append(f"\n{project_state_block}")
    messages.append({"role": "system", "content": "\n".join(system_parts)})

    # 2. Chat history
    for msg in (chat_history or [])[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue
        api_role = "assistant" if role == "assistant" else "user"
        if len(content) > 500:
            content = content[:500] + "..."
        messages.append({"role": api_role, "content": content})

    # 3. User message with context
    context_parts: List[str] = []
    if uploaded_file_content:
        file_label = uploaded_file_name or "上传文件"
        context_parts.append(f"## 用户上传的文件：{file_label}\n\n{uploaded_file_content}")
        logger.info(f"[AI助手] 注入上传文件内容: {len(uploaded_file_content)} chars")
    if doc_context:
        context_parts.append(f"## 参考文档\n\n{doc_context}")
    if graph_context:
        context_parts.append(f"## 相关工艺知识关系\n\n{graph_context}")

    # User-selected reference materials
    if reference_materials:
        user_materials_context = "\n\n## 用户选中的参考素材\n\n" + "\n\n".join([
            f"### 【{m.get('name', '未命名素材')}】\n{m.get('content', '')}"
            for m in reference_materials
        ])
        context_parts.append(user_materials_context)

    if context_parts:
        user_message = "\n\n".join(context_parts) + f"\n\n## 用户问题\n\n{user_input}\n\n请基于参考文档和对话历史回答用户问题。如果参考文档中没有相关信息，请如实告知。"
    else:
        user_message = user_input

    messages.append({"role": "user", "content": user_message})
    return messages


def _save_memory(
    session_id: Optional[str],
    user_input: str,
    content: str,
    project_id: Optional[int] = None,
):
    """Async save conversation memory (fire-and-forget, per-project scoped)."""
    if not session_id:
        return
    try:
        if project_id is not None:
            from app.services.memory_service import get_project_memory_service

            get_project_memory_service(project_id).save_summary_async(
                session_id, user_input, content
            )
        else:
            from app.services.hierarchical_context import hierarchical_context
            hierarchical_context._memory_service.save_summary_async(
                session_id, user_input, content
            )
    except Exception as e:
        logger.warning(f"[AI助手] 记忆保存跳过: {e}")


def _update_project_state(
    project_id: Optional[int],
    session_id: Optional[str],
    user_input: str,
    intent_type: Optional[str] = None,
    focus_chapters: Optional[List[str]] = None,
    output_summary: Optional[dict] = None,
):
    """Roll the project working state forward after one turn (fire-and-forget)."""
    if project_id is None:
        return
    try:
        from app.services.project_state_service import project_state_service

        project_state_service.update_from_turn(
            project_id, session_id, user_input, intent_type, focus_chapters,
            output_summary=output_summary,
        )
    except Exception as e:
        logger.warning(f"[AI助手] 项目状态更新跳过: {e}")


def _persist_turn(
    session_id: Optional[str],
    project_id: Optional[int],
    user_input: str,
    content: str,
    intent_type: Optional[str] = None,
    focus_chapters: Optional[List[str]] = None,
    output_summary: Optional[dict] = None,
):
    """One call per completed turn: conversation memory + project state roll.

    Single entry for ALL output paths (template / markdown / sub-agent /
    streaming fallback) AND for future workflows (e.g. the dialog-edit line):
    any new workflow that produces a turn should call THIS, so state/memory
    stay consistent no matter which path the user took.
    output_summary: template-output paths pass {"chapters": [...], "warnings_count": n}
    so later turns can reference "刚才生成的那篇" (outputs.generated registry).
    """
    _save_memory(session_id, user_input, content, project_id=project_id)
    _update_project_state(
        project_id, session_id, user_input,
        intent_type=intent_type, focus_chapters=focus_chapters,
        output_summary=output_summary,
    )


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


# ==================== Template Export ====================

class TemplateExportRequest(BaseModel):
    """Template PDF export request."""
    template_id: str = Field(..., description="Template ID")
    structured_doc: Dict[str, Any] = Field(..., description="Structured document data")
    footer_values: Optional[Dict[str, Any]] = Field(default=None, description="Footer field values")
    project_id: Optional[int] = Field(None, description="Project ID")


@router.post("/export/template-pdf")
async def export_template_pdf(request: TemplateExportRequest):
    """Export a template-driven document as PDF.

    Generates a complete PDF with cover page, structured tables,
    and footer signatures based on the template definition.
    """
    import tempfile
    from fastapi.responses import FileResponse

    from app.services.template_loader import load_template
    from app.services.template_pdf_export import export_template_pdf as do_export

    try:
        template = load_template(request.template_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {request.template_id}",
        )

    footer_values = request.footer_values or {}

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            output_path = tmp.name

        result_path = do_export(
            template=template,
            structured_doc=request.structured_doc,
            footer_values=footer_values,
            output_path=output_path,
        )

        return FileResponse(
            path=result_path,
            media_type="application/pdf",
            filename=f"{template.get('template_name', 'document')}.pdf",
        )

    except Exception as e:
        logger.error(f"Template PDF export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF export failed: {str(e)}",
        )
