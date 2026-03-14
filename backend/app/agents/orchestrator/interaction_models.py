"""
交互消息模型

定义系统与用户的交互消息格式
"""
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class InteractionType(str, Enum):
    """交互类型"""
    INFO_REQUEST = "info_request"      # 请求信息
    PREVIEW = "preview"                # 预览结果
    CONFIRMATION = "confirmation"      # 确认请求
    PROGRESS = "progress"              # 进度更新
    RESULT = "result"                  # 最终结果
    ERROR = "error"                    # 错误


class InputType(str, Enum):
    """用户输入类型"""
    TEXT = "text"        # 文字输入
    IMAGE = "image"      # 图片
    FILE = "file"        # 文件
    FOLDER = "folder"    # 文件夹


class MissingInfoItem(BaseModel):
    """缺失信息项"""
    name: str                              # 信息名称
    description: str                       # 描述
    example: Optional[str] = None          # 示例值
    impact: str                            # 缺失的影响说明
    priority: str = "medium"               # high/medium/low
    input_type: str = "text"               # text/image/file/folder


class ConfirmOption(BaseModel):
    """确认选项"""
    label: str           # 显示文本
    value: str           # 选项值
    description: Optional[str] = None  # 选项描述


class BaseInteractionMessage(BaseModel):
    """基础交互消息"""
    interaction_type: InteractionType
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    requires_response: bool = True  # 是否需要用户响应


class InfoRequestMessage(BaseInteractionMessage):
    """信息请求消息"""
    interaction_type: InteractionType = InteractionType.INFO_REQUEST
    message: str                                    # 主消息
    missing_items: List[MissingInfoItem]            # 缺失的信息项
    suggestions: List[str] = []                     # 建议的回复
    can_skip: bool = False                          # 是否可以跳过

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_type": "info_request",
                "message": "检测到以下信息缺失，需要您确认：",
                "missing_items": [
                    {
                        "name": "螺钉材料",
                        "description": "不锈钢/碳钢？",
                        "example": "不锈钢",
                        "impact": "影响力矩计算±30%",
                        "priority": "high",
                        "input_type": "text"
                    }
                ],
                "suggestions": ["不锈钢A2-70", "碳钢8.8"],
                "can_skip": False
            }
        }


class PreviewMessage(BaseInteractionMessage):
    """预览消息（简化版）"""
    interaction_type: InteractionType = InteractionType.PREVIEW
    direction: str              # 处理方向：将怎么处理
    expected_result: str        # 大概结果：会得到什么

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_type": "preview",
                "direction": "将计算M8不锈钢(A2-70)螺钉连接铝合金的拧紧力矩",
                "expected_result": "输出推荐的力矩范围值（Nm）和对应预紧力"
            }
        }


class ConfirmationMessage(BaseInteractionMessage):
    """确认消息"""
    interaction_type: InteractionType = InteractionType.CONFIRMATION
    message: str                                    # 主消息
    options: List[ConfirmOption]                    # 选项列表
    preview: Optional[PreviewMessage] = None        # 关联的预览

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_type": "confirmation",
                "message": "确认开始执行？",
                "options": [
                    {"label": "确认执行", "value": "confirm", "description": "开始处理"},
                    {"label": "修改信息", "value": "modify", "description": "返回修改"},
                    {"label": "取消", "value": "cancel", "description": "取消任务"}
                ]
            }
        }


class ProgressMessage(BaseInteractionMessage):
    """进度消息"""
    interaction_type: InteractionType = InteractionType.PROGRESS
    current_step: str                  # 当前步骤
    total_steps: int                   # 总步骤数
    step_description: str              # 步骤描述
    percentage: int                    # 进度百分比

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_type": "progress",
                "current_step": "2",
                "total_steps": 4,
                "step_description": "正在检索知识库...",
                "percentage": 50,
                "requires_response": False
            }
        }


class ResultMessage(BaseInteractionMessage):
    """结果消息"""
    interaction_type: InteractionType = InteractionType.RESULT
    success: bool                       # 是否成功
    message: str                        # 结果消息
    data: Optional[Dict[str, Any]] = None  # 结果数据
    suggestions: List[str] = []          # 后续建议

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_type": "result",
                "success": True,
                "message": "处理完成",
                "data": {"result": "..."},
                "suggestions": ["您可以下载结果", "继续编辑"],
                "requires_response": False
            }
        }


class ErrorMessage(BaseInteractionMessage):
    """错误消息"""
    interaction_type: InteractionType = InteractionType.ERROR
    error_code: str                      # 错误代码
    error_message: str                   # 错误消息
    suggestions: List[str] = []          # 建议的解决方案
    can_retry: bool = True               # 是否可以重试

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_type": "error",
                "error_code": "PROCESSING_FAILED",
                "error_message": "处理过程中发生错误",
                "suggestions": ["请重试", "联系支持"],
                "can_retry": True
            }
        }


# 通用响应类型
InteractionMessage = Union[
    InfoRequestMessage,
    PreviewMessage,
    ConfirmationMessage,
    ProgressMessage,
    ResultMessage,
    ErrorMessage
]


class UserResponse(BaseModel):
    """用户响应"""
    session_id: str
    response_type: InputType = InputType.TEXT
    content: Union[str, List[str], Dict[str, Any]]  # 文字/文件路径/结构化数据
    selected_option: Optional[str] = None  # 如果是选择选项
    additional_info: Optional[Dict[str, Any]] = None  # 附加信息
