"""
共享日志模块 - 结构化日志实现
"""
import logging
import time
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger
from contextvars import ContextVar
import uuid

# 请求上下文变量
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')
session_id_var: ContextVar[str] = ContextVar('session_id', default='')


class StructuredLogger(logging.Logger):
    """结构化日志记录器 - 支持关键字参数"""

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1, **kwargs):
        """重写_log方法以支持结构化数据"""
        if extra is None:
            extra = {}

        # 将kwargs中的数据添加到extra中
        extra.update(kwargs)

        # 调用父类的_log方法
        super()._log(level, msg, args, exc_info=exc_info, extra=extra, stack_info=stack_info, stacklevel=stacklevel)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定义JSON格式化器"""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """添加自定义字段"""
        super().add_fields(log_record, record, message_dict)

        # 添加时间戳
        log_record['timestamp'] = time.time()
        log_record['datetime'] = self.formatTime(record)

        # 添加上下文信息
        log_record['correlation_id'] = request_id_var.get() or str(uuid.uuid4())
        log_record['user_id'] = user_id_var.get()
        log_record['session_id'] = session_id_var.get()

        # 添加源信息
        log_record['source'] = f"{record.pathname}:{record.lineno}"
        log_record['function'] = record.funcName

        # 添加性能指标
        if hasattr(record, 'duration_ms'):
            log_record['duration_ms'] = record.duration_ms

        # 添加extra中的结构化数据
        if hasattr(record, 'extra_data'):
            log_record.update(record.extra_data)

        # 移除不需要的字段
        for key in ['name', 'msg', 'args', 'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process']:
            log_record.pop(key, None)


# 注册自定义Logger类
logging.setLoggerClass(StructuredLogger)

def get_logger(name: str) -> StructuredLogger:
    """
    获取结构化日志记录器

    使用方式:
        from app.shared.logging import get_logger
        logger = get_logger(__name__)
        logger.info("user_created", user_id="123", role="admin")
    """
    logger = logging.getLogger(name)

    # 如果logger已经有处理器，直接返回
    if logger.handlers:
        return logger

    # 设置日志级别
    logger.setLevel(logging.DEBUG)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # 设置JSON格式化器
    formatter = CustomJsonFormatter()
    console_handler.setFormatter(formatter)

    # 添加处理器到logger
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger


class LoggingContext:
    """日志上下文管理器 - 用于绑定请求级数据"""

    def __init__(self, **kwargs):
        self.data = kwargs
        self.tokens = {}

    def __enter__(self):
        """进入上下文"""
        for key, value in self.data.items():
            if key == 'request_id':
                self.tokens['request_id'] = request_id_var.set(value)
            elif key == 'user_id':
                self.tokens['user_id'] = user_id_var.set(value)
            elif key == 'session_id':
                self.tokens['session_id'] = session_id_var.set(value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        for key, token in self.tokens.items():
            if key == 'request_id':
                request_id_var.reset(token)
            elif key == 'user_id':
                user_id_var.reset(token)
            elif key == 'session_id':
                session_id_var.reset(token)


def bind_context(**kwargs) -> LoggingContext:
    """
    绑定日志上下文

    使用方式:
        with bind_context(request_id="req-123", user_id="user-456"):
            logger.info("operation_started")
            # ... 执行操作
            logger.info("operation_completed", duration_ms=100)
    """
    return LoggingContext(**kwargs)


class Timer:
    """性能计时器 - 用于记录操作耗时"""

    def __init__(self, logger: logging.Logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None

    def __enter__(self):
        """开始计时"""
        self.start_time = time.time()
        self.logger.info(f"{self.operation}_started", **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """结束计时"""
        duration = (time.time() - self.start_time) * 1000  # 转换为毫秒

        # 添加耗时到上下文
        self.context['duration_ms'] = duration

        if exc_type is None:
            self.logger.info(f"{self.operation}_completed", **self.context)
        else:
            self.logger.exception(f"{self.operation}_failed", **self.context)


def timer(logger: logging.Logger, operation: str, **context) -> Timer:
    """
    创建性能计时器

    使用方式:
        logger = get_logger(__name__)
        with timer(logger, "database_query", query="SELECT * FROM users"):
            # ... 执行数据库查询
            pass
    """
    return Timer(logger, operation, **context)