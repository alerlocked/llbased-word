"""
共享配置模块 - 集中管理配置常量

注意: MinerU配置已迁移到 app.config.py，这里保留向后兼容的别名
"""
from typing import Set

# 从主配置导入MinerU配置，保持向后兼容
try:
    from app.config import settings as _settings
    _mineru_settings_available = True
except ImportError:
    _mineru_settings_available = False

# 不可靠域名列表 - 集中管理，避免重复定义
UNRELIABLE_DOMAINS: Set[str] = {
    # 之前定义的不可靠域名
    "baidu.com",
    "baiducontent.com",
    "bdstatic.com",
    "bilibili.com",
    "csdn.net",
    "csdnimg.cn",
    "jianshu.com",
    "juejin.cn",
    "oschina.net",
    "segmentfault.com",
    "zhihu.com",
    "zhimg.com",
    "weibo.com",
    "weibo.cn",
    "qq.com",
    "qpic.cn",
    "sina.com.cn",
    "sinaimg.cn",
    "sohu.com",
    "163.com",
    "126.com",
    "yeah.net",
    "youdao.com",
    "cnblogs.com",
    "iteye.com",
    "github.com",
    "gitlab.com",
    "stackoverflow.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",

    # 从aliyun_search.py提取的低质量来源
    "xdnimg.13520.info",
    "youpinqf.com",
    "jiutuvip.com",
    "chongso.com"
}

# 调试配置
DEBUG_CONFIG = {
    "log_file": "debug_aliyun_search.log",
    "log_level": "INFO",
    "max_log_size": 10 * 1024 * 1024,  # 10MB
    "log_rotation": True
}

# API配置
API_CONFIG = {
    "timeout": 30,
    "retry_count": 3,
    "retry_delay": 1,
    "max_results": 20
}

# 搜索配置
SEARCH_CONFIG = {
    "safe_search": True,
    "filter_unreliable": True,
    "max_image_size": 5 * 1024 * 1024,  # 5MB
    "supported_formats": ["jpg", "jpeg", "png", "gif", "webp"]
}

# CSV导出配置
CSV_EXPORT_CONFIG = {
    "encoding": "utf-8-sig",  # UTF-8 with BOM for Excel compatibility
    "delimiter": ",",
    "quotechar": '"',
    "include_metadata": True,
    "include_headers": True,
    "date_format": "%Y-%m-%d",
    "max_rows_per_file": 100000,  # Prevent memory issues with large tables
    "strip_whitespace": True
}

# PDF解析器配置 - 双复杂度模式
PDF_PARSER_CONFIG = {
    # 通用配置
    "text_extraction_quality": "high",
    "image_extraction_enabled": False,
    "enable_caching": True,
    "accuracy_threshold": 0.97,  # ≥97% accuracy requirement

    # 双复杂度模式配置
    "force_mode": None,  # None(自动) | "simple" | "complex"
    "quick_detect_pages": 5,  # 快速检测时扫描的页数

    # 向后兼容
    "table_detection_threshold": 0.8,
    "enable_multipage_merge": True,
}

# MinerU VLM高精度表格解析配置
# 用于复杂模式（有表格的PDF）
# RTX 5080需要使用CUDA 12.8版本的PyTorch
# 配置已迁移到 app.config.py，这里使用动态获取
def _get_mineru_config() -> dict:
    """动态获取MinerU配置，优先从主配置获取"""
    if _mineru_settings_available:
        return {
            "enabled": _settings.MINERU_ENABLED,
            "backend": _settings.MINERU_BACKEND,
            "table_enable": _settings.MINERU_TABLE_ENABLE,
            "lang": _settings.MINERU_LANG,
            "enable_table_merge": _settings.MINERU_TABLE_MERGE_ENABLE,
            "fallback_to_pdfplumber": _settings.MINERU_FALLBACK_TO_PDFPLUMBER,
            "timeout_seconds": _settings.MINERU_TIMEOUT_SECONDS,
            "parse_method": _settings.MINERU_PARSE_METHOD,
            "table_model": _settings.MINERU_TABLE_MODEL,
            "version": _settings.MINERU_VERSION,
        }
    # 回退到默认配置
    return {
        "enabled": True,
        "backend": "vlm-auto-engine",
        "table_enable": True,
        "lang": "ch",
        "enable_table_merge": True,
        "fallback_to_pdfplumber": False,
        "timeout_seconds": 600,
        "parse_method": "auto",
        "table_model": "rapid_table",
        "version": "3.4.0",
    }

MINERU_VLM_CONFIG = _get_mineru_config()

# 向后兼容别名
MINERU_CONFIG = MINERU_VLM_CONFIG

# ============ Search Agent 配置 ============
import os

# RAG 服务开关（默认禁用）
ENABLE_RAG = os.getenv("ENABLE_RAG", "false").lower() == "true"

# Search Agent 缓存配置
SEARCH_AGENT_CONFIG = {
    "cache_size": int(os.getenv("SEARCH_AGENT_CACHE_SIZE", "1000")),
    "cache_ttl": int(os.getenv("SEARCH_AGENT_CACHE_TTL", "300")),  # 秒
}

# Search Agent Token 预算配置
SEARCH_TOKEN_CONFIG = {
    "max_tokens": int(os.getenv("SEARCH_MAX_TOKENS", "4000")),
    "files_ratio": float(os.getenv("SEARCH_FILES_RATIO", "0.6")),
    "knowledge_ratio": float(os.getenv("SEARCH_KNOWLEDGE_RATIO", "0.3")),
    "buffer_ratio": float(os.getenv("SEARCH_BUFFER_RATIO", "0.1")),
}

# 多轮迭代配置
ITERATION_CONFIG = {
    "max_iterations": int(os.getenv("MAX_ITERATIONS", "3")),
    "timeout": int(os.getenv("ITERATION_TIMEOUT", "60")),  # 秒
}