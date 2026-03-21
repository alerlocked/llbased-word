"""
应用配置文件
使用pydantic-settings管理配置项
工艺文件辅助编辑系统
"""
from pathlib import Path
from typing import Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """应用配置类"""

    # 应用基本配置
    APP_NAME: str = "智能工艺文件辅助编辑系统"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # 数据存储路径配置
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = Path.home() / "CraftDocApp" / "data"
    DB_DIR: Path = DATA_DIR / "database"
    FIGURES_DIR: Path = DATA_DIR / "figures"  # 提取的图片存储目录
    STATIC_DIR: Path = BASE_DIR / "static"  # 静态文件目录

    # 数据库配置
    DATABASE_URL: str = f"sqlite:///{DB_DIR}/craftdoc.db"

    # Redis配置（用于Celery任务队列）
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

    # 通义千问统一配置
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 文本API
    DASHSCOPE_HTTP_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"  # DashScope HTTP API
    QWEN_TEXT_MODEL: str = "qwen-plus"  # 文本生成模型
    QWEN_VL_MODEL: str = "qwen-vl-max"  # 视觉语言模型（用于OCR和图片理解）

    # 阿里云检索服务配置
    ALIYUN_ACCESS_KEY_ID: str = ""
    ALIYUN_ACCESS_KEY_SECRET: str = ""
    ALIYUN_IQS_ENDPOINT: str = "iqs.cn-zhangjiakou.aliyuncs.com"
    ALIYUN_IMAGESEARCH_ENDPOINT: str = "imagesearch.cn-shanghai.aliyuncs.com"
    ALIYUN_IMAGESEARCH_INSTANCE_NAME: str = "craftdoc_images"
    ALIYUN_IMAGESEARCH_REGION: str = "cn-shanghai"

    # 文件上传限制
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_DOCUMENT_FORMATS: list = [".pdf", ".docx", ".doc", ".txt"]

    # LangChain配置
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_PROJECT: str = "craftdoc-agent"

    # OpenAI配置（复用通义千问配置）
    OPENAI_API_KEY: str = ""  # 将在__init__后设置
    OPENAI_API_BASE: str = ""  # 将在__init__后设置

    # Embedding配置
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"

    # 硅基流动配置 (用于Embedding)
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"

    # DeepSeek配置 (用于LLM推理)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Agent配置
    AGENT_MAX_ITERATIONS: int = 10
    AGENT_TEMPERATURE: float = 0.3

    # 任务记忆Repository配置
    REPOSITORY_TYPE: str = "json"  # json | sqlite
    TASK_DATA_DIR: Path = Path("data/tasks")  # JSON文件存储目录
    SQLITE_DB_PATH: Path = Path("data/tasks.db")  # SQLite数据库文件路径

    # 上下文工程配置
    CONTEXT_COMPRESSION_THRESHOLD: float = 0.85  # 压缩触发阈值（窗口85%）
    CONTEXT_MODEL_WINDOW_SIZE: int = 32000  # 模型上下文窗口大小
    CONTEXT_MAX_HISTORY_TURNS: int = 15  # 最大历史轮次
    CONTEXT_LTM_RETRIEVE_TOP_K: int = 3  # LTM检索Top-K
    CONTEXT_TOOL_SUBSET_TOP_K: int = 5  # 工具子集Top-K
    CONTEXT_RELEVANCE_THRESHOLD: float = 0.7  # 相关性阈值
    CONTEXT_TOKEN_EFFICIENCY_TARGET: float = 0.6  # Token效率目标值
    CONTEXT_STM_MAX_LENGTH: int = 10  # 短期记忆最大长度（轮次）

    # 语义去重配置
    CONTEXT_SEMANTIC_DEDUP_THRESHOLD: float = 0.85  # 语义相似度阈值，超过此值视为重复

    # ============ MinerU 配置 (集中管理) ============
    # 版本锁定 - 确保API稳定性
    MINERU_VERSION: str = "0.7.6"

    # 后端选择: pipeline / vlm-auto-engine / hybrid-auto-engine
    MINERU_BACKEND: str = "vlm-auto-engine"

    # VLM 配置
    MINERU_VLM_MODEL: str = "default"
    MINERU_VLM_DEVICE: str = "cuda"

    # 解析参数
    MINERU_PARSE_METHOD: str = "auto"  # auto / txt / ocr
    MINERU_TABLE_ENABLE: bool = True
    MINERU_FORMULA_ENABLE: bool = False
    MINERU_LANG: str = "ch"  # 中文优化

    # 表格处理
    MINERU_TABLE_MERGE_ENABLE: bool = True
    MINERU_TABLE_MODEL: str = "rapid_table"

    # 输出配置
    MINERU_OUTPUT_FORMAT: str = "html"
    MINERU_IMAGE_DPI: int = 200

    # 性能配置
    MINERU_TIMEOUT_SECONDS: int = 600
    MINERU_FALLBACK_TO_PDFPLUMBER: bool = False  # VLM模式下不回退
    MINERU_ENABLED: bool = True

    # ============ VLService 配置 (多后端 + 并行处理) ============
    # 后端选择: mineru / qwen
    VL_SERVICE_BACKEND: str = "mineru"
    # 并行处理数（避免内存溢出，默认4）
    VL_SERVICE_MAX_WORKERS: int = 4
    # MinerU失败时是否回退到Qwen
    VL_SERVICE_FALLBACK_TO_QWEN: bool = True

    # 结构化提取配置
    CONTEXT_STRUCTURED_EXTRACTION_ENABLED: bool = True  # 是否启用结构化提取
    CONTEXT_DIMENSION_KEYWORDS: Dict[str, List[str]] = {
        "工艺类型": ["加工", "装配", "热处理", "表面处理", "检验"],
        "零件特征": ["尺寸", "公差", "材料", "精度", "表面粗糙度"],
        "设备要求": ["设备", "机床", "夹具", "刀具", "量具"],
        "工艺参数": ["转速", "进给", "切削深度", "温度", "时间"],
        "质量要求": ["检验", "测量", "合格", "精度", "表面质量"]
    }

    # 意图识别配置
    CONTEXT_INTENT_CLASSIFICATION_ENABLED: bool = True  # 是否启用意图识别
    CONTEXT_INTENT_KEYWORDS: Dict[str, List[str]] = {
        "补充信息": ["补充", "还有", "另外", "1", "2", "3", "4", "5", "再", "继续"],
        "询问细节": ["什么", "如何", "为什么", "？", "?", "怎么", "能否"],
        "要求修改": ["修改", "改", "调整", "不要", "删除", "去掉", "换"],
        "确认方案": ["确认", "选择", "采用", "方案", "就这个", "确定"]
    }

    # 模型配置 - pydantic v2语法
    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    def __init__(self, **kwargs):
        """初始化配置，设置OpenAI兼容配置"""
        super().__init__(**kwargs)
        # 复用通义千问配置给OpenAI SDK
        if not self.OPENAI_API_KEY:
            self.OPENAI_API_KEY = self.DASHSCOPE_API_KEY
        if not self.OPENAI_API_BASE:
            self.OPENAI_API_BASE = self.DASHSCOPE_BASE_URL

# 创建全局配置实例
settings = Settings()

# 确保目录存在
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.DB_DIR.mkdir(parents=True, exist_ok=True)
settings.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
settings.TASK_DATA_DIR.mkdir(parents=True, exist_ok=True)
