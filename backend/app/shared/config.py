"""
共享配置模块 - 集中管理配置常量
"""
from typing import Set

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
MINERU_VLM_CONFIG = {
    "enabled": True,
    "backend": "vlm-auto-engine",  # VLM高精度模式，自动选择最佳引擎
    "table_enable": True,
    "lang": "ch",  # 中文优化
    "enable_table_merge": True,
    "fallback_to_pdfplumber": False,  # VLM模式下不回退
    "timeout_seconds": 600,
    "parse_method": "auto",
}

# 向后兼容别名
MINERU_CONFIG = MINERU_VLM_CONFIG