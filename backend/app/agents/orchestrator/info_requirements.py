"""
信息需求模板定义

定义不同任务类型需要的信息，每个任务类型定义：
- required: 必需信息（缺失则无法继续）
- optional: 可选信息（缺失可用默认值）
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from app.shared.logging import get_logger

logger = get_logger(__name__)


class InfoPriority(str, Enum):
    """信息优先级"""
    HIGH = "high"      # 高优先级：必须提供
    MEDIUM = "medium"  # 中优先级：影响结果质量
    LOW = "low"       # 低优先级：可使用默认值


class InputType(str, Enum):
    """用户输入类型"""
    TEXT = "text"        # 文字输入
    IMAGE = "image"      # 图片
    FILE = "file"        # 文件
    FOLDER = "folder"    # 文件夹


@dataclass
class InfoItem:
    """信息项定义"""
    name: str                          # 信息名称（用于识别）
    description: str                   # 描述（给用户看）
    example: Optional[str] = None       # 示例值
    default_value: Optional[str] = None  # 默认值
    impact: Optional[str] = None        # 缺失影响说明
    priority: InfoPriority = InfoPriority.MEDIUM
    input_type: InputType = InputType.TEXT
    aliases: List[str] = None            # 别名（用于匹配）

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []

    def matches(self, key: str) -> bool:
        """检查给定的key是否匹配此信息项"""
        key_lower = key.lower()
        if self.name.lower() == key_lower:
            return True
        for alias in (self.aliases or []):
            if alias.lower() == key_lower:
                return True
        return False


@dataclass
class TaskInfoRequirements:
    """任务类型的信息需求"""
    task_type: str                           # 任务类型标识
    description: str                         # 任务描述
    required: List[InfoItem]                 # 必需信息
    optional: List[InfoItem]                 # 可选信息
    keywords: List[str] = None               # 触发关键词

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


# ============== 预定义的信息需求模板 ==============

INFO_REQUIREMENTS: Dict[str, TaskInfoRequirements] = {
    # ============== 计算类任务 ==============
    "calculate_torque": TaskInfoRequirements(
        task_type="calculate_torque",
        description="计算螺栓拧紧力矩",
        required=[
            InfoItem(
                name="screw_spec",
                description="螺钉规格",
                example="M8",
                impact="规格决定螺纹参数和力矩系数",
                priority=InfoPriority.HIGH,
                aliases=["螺钉规格", "螺丝规格", "螺栓规格", "规格"]
            ),
            InfoItem(
                name="material",
                description="螺钉材料",
                example="不锈钢",
                impact="不同材料的摩擦系数不同，力矩差异可达±30%",
                priority=InfoPriority.HIGH,
                aliases=["材料", "螺钉材料", "螺丝材料"]
            ),
            InfoItem(
                name="strength_grade",
                description="强度等级",
                example="A2-70",
                impact="决定最大允许预紧力和力矩范围",
                priority=InfoPriority.HIGH,
                aliases=["强度等级", "等级", "性能等级"]
            ),
        ],
        optional=[
            InfoItem(
                name="connected_material",
                description="被连接件材料",
                example="铝合金",
                default_value="钢",
                impact="影响螺纹啮合长度设计",
                priority=InfoPriority.MEDIUM,
                aliases=["被连接件", "连接件材料"],
            ),
            InfoItem(
                name="lubrication",
                description="润滑条件",
                example="机油润滑",
                default_value="干摩擦",
                impact="影响力矩系数K值",
                priority=InfoPriority.LOW,
                aliases=["润滑", "润滑状态"],
            ),
        ],
        keywords=["力矩", "拧紧", "扭矩", "预紧力", "螺钉", "螺栓"],
    ),

    # ============== 编辑类任务 ==============
    "edit_document": TaskInfoRequirements(
        task_type="edit_document",
        description="编辑工艺文件",
        required=[
            InfoItem(
                name="target_section",
                description="目标章节/位置",
                example="工序3",
                impact="需要知道修改哪个部分",
                priority=InfoPriority.HIGH,
                aliases=["位置", "章节", "修改位置", "目标位置"],
            ),
            InfoItem(
                name="edit_content",
                description="编辑内容/修改要求",
                example="将转速改为2000rpm",
                impact="需要知道具体要改什么",
                priority=InfoPriority.HIGH,
                aliases=["内容", "修改内容", "要求", "修改要求"],
            ),
        ],
        optional=[
            InfoItem(
                name="reference_docs",
                description="参考文档",
                example="工艺标准手册.pdf",
                impact="参考文档可提高修改准确性",
                priority=InfoPriority.MEDIUM,
                input_type=InputType.FILE,
                aliases=["参考", "参考资料", "文档"],
            ),
        ],
        keywords=["编辑", "修改", "改", "更新", "工艺文件"],
    ),

    # ============== 创建类任务 ==============
    "create_document": TaskInfoRequirements(
        task_type="create_document",
        description="创建工艺文件",
        required=[
            InfoItem(
                name="document_type",
                description="文档类型",
                example="加工工艺卡",
                impact="决定使用哪个模板",
                priority=InfoPriority.HIGH,
                aliases=["类型", "文档类型", "工艺类型"],
            ),
            InfoItem(
                name="part_info",
                description="零件信息",
                example="零件号、材料、数量",
                impact="基础信息必须明确",
                priority=InfoPriority.HIGH,
                aliases=["零件", "零件信息", "工件"],
            ),
        ],
        optional=[
            InfoItem(
                name="template",
                description="模板选择",
                example="标准模板",
                default_value="default",
                impact="使用不同模板生成不同格式",
                priority=InfoPriority.LOW,
            ),
            InfoItem(
                name="reference_docs",
                description="参考文档",
                impact="参考已有文档可提高效率",
                priority=InfoPriority.MEDIUM,
                input_type=InputType.FILE,
            ),
        ],
        keywords=["创建", "新建", "生成", "制作", "工艺文件"],
    ),

    # ============== 检索类任务 ==============
    "search_knowledge": TaskInfoRequirements(
        task_type="search_knowledge",
        description="检索工艺知识",
        required=[
            InfoItem(
                name="query",
                description="检索内容",
                example="数控车削参数",
                impact="需要知道要查什么",
                priority=InfoPriority.HIGH,
                aliases=["查询", "搜索", "查找"],
            ),
        ],
        optional=[
            InfoItem(
                name="filter_scope",
                description="检索范围",
                example="机械加工",
                impact="限定范围可提高检索精度",
                priority=InfoPriority.LOW,
            ),
        ],
        keywords=["查找", "搜索", "检索", "查询", "知识库"],
    ),

    # ============== 校对类任务（独立调用） ==============
    "proofread": TaskInfoRequirements(
        task_type="proofread",
        description="校对工艺内容",
        required=[
            InfoItem(
                name="content",
                description="待校对内容",
                impact="必须提供要校对的内容",
                priority=InfoPriority.HIGH,
                input_type=InputType.TEXT,
                aliases=["内容", "文本", "工艺内容"],
            ),
        ],
        optional=[
            InfoItem(
                name="check_type",
                description="检查类型",
                example="all",
                default_value="all",
                impact="可限定检查范围",
                priority=InfoPriority.LOW,
                aliases=["类型", "检查类型"],
            ),
            InfoItem(
                name="target_standard",
                description="目标标准",
                example="企业标准",
                default_value="enterprise_standard",
                priority=InfoPriority.LOW,
            ),
        ],
        keywords=["校对", "检查", "审核", "术语", "格式"],
    ),

    # ============== 审查类任务（独立调用） ==============
    "review": TaskInfoRequirements(
        task_type="review",
        description="审查工艺内容",
        required=[
            InfoItem(
                name="content",
                description="待审查内容",
                impact="必须提供要审查的内容",
                priority=InfoPriority.HIGH,
                input_type=InputType.TEXT,
            ),
        ],
        optional=[
            InfoItem(
                name="check_type",
                description="检查类型",
                example="all",
                default_value="all",
                priority=InfoPriority.LOW,
            ),
            InfoItem(
                name="standards",
                description="审查标准",
                example="企业标准,安全标准",
                default_value="enterprise,safety",
                priority=InfoPriority.MEDIUM,
            ),
        ],
        keywords=["审查", "合规", "风险", "安全"],
    ),
}


def get_info_requirements(task_type: str) -> Optional[TaskInfoRequirements]:
    """
    获取指定任务类型的信息需求

    Args:
        task_type: 任务类型

    Returns:
        信息需求定义，如果不存在则返回None
    """
    return INFO_REQUIREMENTS.get(task_type)


def get_all_task_types() -> List[str]:
    """获取所有支持的任务类型"""
    return list(INFO_REQUIREMENTS.keys())


def detect_task_type(user_input: str) -> Optional[str]:
    """
    根据用户输入检测任务类型

    Args:
        user_input: 用户输入

    Returns:
        检测到的任务类型，如果无法确定则返回None
    """
    input_lower = user_input.lower()

    best_match = None
    best_score = 0

    for task_type, requirements in INFO_REQUIREMENTS.items():
        if requirements.keywords:
            score = sum(1 for kw in requirements.keywords if kw in input_lower)
            if score > best_score:
                best_score = score
                best_match = task_type

    return best_match if best_score > 0 else None


def register_info_requirements(
    task_type: str,
    requirements: TaskInfoRequirements
):
    """
    注册新的信息需求模板

    Args:
        task_type: 任务类型
        requirements: 信息需求定义
    """
    INFO_REQUIREMENTS[task_type] = requirements
    logger.info("info_requirements_registered", task_type=task_type)
