"""
日志配置模块
使用Python标准logging库，模拟Winston风格的多级别日志
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from pythonjsonlogger import jsonlogger

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（控制台输出）"""
    
    # ANSI颜色代码
    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 紫色
        "RESET": "\033[0m",       # 重置
    }
    
    def format(self, record):
        """格式化日志记录"""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        
        # 格式: [时间] [级别] [模块] 消息
        record.levelname = f"{color}{record.levelname}{reset}"
        record.name = f"{color}{record.name}{reset}"
        
        return super().format(record)

def setup_logger(name: str = "journalist_app", level: str = "INFO") -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVELS.get(level, logging.INFO))
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 确保日志传播到根日志记录器（用于调试）
    logger.propagate = False
    
    # 控制台处理器（彩色输出）
    # 强制使用 UTF-8 编码以支持 emoji 和中文
    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    console_handler = logging.StreamHandler(utf8_stdout)
    console_handler.setLevel(logging.DEBUG)  # 控制台显示所有级别的日志
    console_formatter = ColoredFormatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 确保日志立即刷新
    console_handler.flush()
    
    # 文件处理器（JSON格式，便于日志分析）
    from app.config import settings
    log_dir = settings.DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    
    # JSON格式化器
    json_formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)
    
    return logger

# 创建全局日志实例
logger = setup_logger()

# 便捷函数
def log_workflow(workflow_name: str, step: str, details: dict = None):
    """
    记录工作流日志
    
    Args:
        workflow_name: 工作流名称（如"音频转写"）
        step: 步骤名称（如"上传文件"）
        details: 详细信息字典
    """
    message = f"[工作流: {workflow_name}] [步骤: {step}]"
    if details:
        message += f" {details}"
    logger.info(message)

def log_api_call(service: str, endpoint: str, status: str, duration_ms: float = None):
    """
    记录API调用日志
    
    Args:
        service: 服务名称（如"阿里云ASR"）
        endpoint: 接口端点
        status: 调用状态（success/error）
        duration_ms: 调用耗时（毫秒）
    """
    message = f"[API调用] {service} - {endpoint} - {status}"
    if duration_ms:
        message += f" - {duration_ms:.2f}ms"
    logger.info(message)




















