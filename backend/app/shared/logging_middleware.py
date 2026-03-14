"""
日志中间件 - 用于自动记录请求信息和绑定上下文
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.shared.logging import get_logger, bind_context

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件 - 自动记录请求日志和绑定上下文"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """处理请求和响应"""
        # 生成请求ID
        request_id = str(uuid.uuid4())

        # 从请求头获取用户ID（如果有）
        user_id = request.headers.get("X-User-ID", "")
        session_id = request.headers.get("X-Session-ID", "")

        # 创建日志上下文
        with bind_context(request_id=request_id, user_id=user_id, session_id=session_id):
            # 记录请求开始
            logger.info("request_started",
                       method=request.method,
                       url=str(request.url),
                       client_host=request.client.host if request.client else "unknown",
                       user_agent=request.headers.get("user-agent", ""))

            start_time = time.time()

            try:
                # 调用下一个中间件或路由处理程序
                response = await call_next(request)

                # 计算耗时
                duration = (time.time() - start_time) * 1000

                # 记录请求完成
                logger.info("request_completed",
                           method=request.method,
                           url=str(request.url),
                           status_code=response.status_code,
                           duration_ms=round(duration, 2))

                return response

            except Exception as e:
                # 计算耗时
                duration = (time.time() - start_time) * 1000

                # 记录请求失败
                logger.exception("request_failed",
                               method=request.method,
                               url=str(request.url),
                               duration_ms=round(duration, 2),
                               error_type=type(e).__name__)

                # 重新抛出异常
                raise


def add_logging_middleware(app):
    """添加日志中间件到FastAPI应用"""
    app.add_middleware(LoggingMiddleware)