# -*- coding: utf-8 -*-
"""
FastAPI应用入口文件
启动Web服务器，配置路由和中间件
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from app.api import process, creation, web_image, export, annotation, node_documents, materials
from app.api import task_router, document_router
from app.api import pdf_status, agent, assistant, process_documents, deepseek
from app.api import context
from app.api import draft
from app.api import profile
from app.config import settings
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.services.pdf_queue_manager import get_pdf_queue_manager, PDFTask
from app.services.document_processor import DocumentProcessor
from app.database import SessionLocal
import urllib.request
import urllib.error


# Static MIME mapping — decoupled from system `mimetypes` registry.
# Windows registry may map extensions (e.g. .html) to a wrong Content-Type
# (e.g. "text/utf-8"), breaking browser rendering. We declare types explicitly.
_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".ico": "image/x-icon", ".webp": "image/webp",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf", ".otf": "font/otf",
    ".map": "application/json", ".wasm": "application/wasm", ".txt": "text/plain; charset=utf-8",
}


def _media_type(path) -> str:
    """Explicit Content-Type for a static file, ignoring system mimetypes."""
    return _MEDIA_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


def _check_model_server():
    """Test connectivity to model server at startup. Results printed to terminal."""
    print("=" * 50)
    print("  Model Server Connectivity Check")
    print("=" * 50)

    llm_url = settings.DASHSCOPE_BASE_URL_COMPLEX or settings.DASHSCOPE_BASE_URL
    vlm_url = settings.MINERU_VL_SERVER

    # Check LLM
    llm_ok = False
    try:
        req = urllib.request.Request(f"{llm_url.rstrip('/')}/models", method="GET")
        if settings.DASHSCOPE_API_KEY:
            req.add_header("Authorization", f"Bearer {settings.DASHSCOPE_API_KEY}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            llm_ok = resp.status == 200
            body = resp.read().decode("utf-8")[:200]
        print(f"  LLM  ({llm_url}): OK - {body[:80]}")
    except urllib.error.URLError as e:
        print(f"  LLM  ({llm_url}): FAILED - {e.reason}")
    except Exception as e:
        print(f"  LLM  ({llm_url}): FAILED - {e}")

    # Check VLM (MinerU http-client or qwen_local)
    vlm_ok = False
    if vlm_url:
        try:
            req = urllib.request.Request(f"{vlm_url.rstrip('/')}/models", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                vlm_ok = resp.status == 200
            print(f"  VLM  ({vlm_url}): OK")
        except urllib.error.URLError as e:
            print(f"  VLM  ({vlm_url}): FAILED - {e.reason}")
        except Exception as e:
            print(f"  VLM  ({vlm_url}): FAILED - {e}")
    else:
        print("  VLM  : local mode (built-in transformers, no http VLM server)")

    print("=" * 50)
    if not llm_ok or (vlm_url and not vlm_ok):
        if not llm_ok:
            print("  WARNING: LLM not reachable. AI features will not work!")
        if vlm_url and not vlm_ok:
            print("  WARNING: VLM not reachable. PDF parsing will fail!")
        print("  Quick checks:")
        print("    1. ping model server IP")
        print("    2. Check firewall on model server:")
        print("       ssh root@<server> 'systemctl stop firewalld'")
        print("    3. Check container: ssh root@<server> 'docker ps'")
    print()
    return llm_ok, vlm_ok

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（startup + shutdown）"""
    # === Startup ===
    logger.info("🚀 应用启动中...")
    logger.info(f"📁 数据目录: {settings.DATA_DIR}")

    # 确保必要的目录存在
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.DB_DIR.mkdir(parents=True, exist_ok=True)

    # 初始化数据库（创建新表）
    from app.database import init_db
    init_db()

    # 加载全局工艺知识图谱（跨 profile，持久化 data/knowledge_graph.json）
    from app.services.knowledge_graph import init_craft_kg
    init_craft_kg()

    # 初始化PDF解析队列管理器
    try:
        queue_manager = get_pdf_queue_manager()
        processor = DocumentProcessor()

        async def parse_wrapper(task: PDFTask):
            """Async parser for PDF queue"""
            db = SessionLocal()
            try:
                def on_progress(pct: int, msg: str = ""):
                    queue_manager.update_progress(task.task_id, pct, message=msg)
                return await processor.process_document_from_task(task, db, progress_callback=on_progress)
            except Exception as e:
                logger.error(f"队列任务执行失败: {str(e)}")
                return {"error": str(e)}
            finally:
                db.close()

        queue_manager.set_parser(parse_wrapper)
        logger.info("✅ PDF 队列解析函数已设置")

        await queue_manager.start()
        logger.info("✅ PDF解析队列管理器已初始化")

    except Exception as e:
        logger.warning(f"⚠️ PDF解析队列初始化失败: {e}")

    logger.info("✅ 应用启动完成")
    logger.info("📝 请求日志中间件已启用，所有HTTP请求将被记录")

    # Startup summary
    print("\n" + "=" * 50)
    print(f"  {settings.APP_NAME} v{settings.VERSION}")
    print(f"  http://{settings.HOST}:{settings.PORT}")
    print("=" * 50)
    print(f"  Database  : {settings.DB_DIR / 'craftdoc.db'}")
    print(f"  Data dir  : {settings.DATA_DIR}")
    print(f"  Debug     : {settings.DEBUG}")
    print(f"  PDF Queue : {'OK' if queue_manager else 'FAILED'}")
    vlm_url = settings.MINERU_VL_SERVER
    llm_ok, vlm_ok = _check_model_server()
    if llm_ok:
        print("  LLM       : OK")
    else:
        print("  LLM       : FAILED")
    if vlm_ok:
        print("  VLM       : OK")
    elif vlm_url:
        print("  VLM       : FAILED")
    else:
        print("  VLM       : local mode (built-in)")
    print("=" * 50 + "\n")

    yield  # 应用运行中

    # === Shutdown ===
    logger.info("👋 应用关闭中...")

    # 停止PDF解析队列管理器
    try:
        from app.services.pdf_watcher_service import get_pdf_watcher_service

        # 停止监听服务
        watcher = get_pdf_watcher_service()
        if watcher._is_running:
            await watcher.stop()
            logger.info("✅ PDF监听服务已停止")

        # 停止队列管理器（使用顶层已导入的 get_pdf_queue_manager）
        queue_manager = get_pdf_queue_manager()
        await queue_manager.stop()
        logger.info("✅ PDF队列管理器已停止")

    except Exception as e:
        logger.warning(f"⚠️ 关闭PDF服务时出错: {e}")

    logger.info("👋 应用关闭完成")


# 创建FastAPI应用实例
app = FastAPI(
    title="智能工艺文件辅助编辑系统",
    description="面向工艺师的专业AI辅助编辑工具",
    version="0.1.0",
    lifespan=lifespan,
)

# 全局异常处理器 - 捕获请求验证错误
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """捕获请求验证错误并记录日志"""
    try:
        body = await request.body()
        body_str = body.decode('utf-8')[:1000]  # 限制长度
    except:
        body_str = "无法读取请求体"
    
    logger.error(f"❌ [请求验证] 请求验证失败: {request.method} {request.url}")
    logger.error(f"❌ [请求验证] 错误详情: {exc.errors()}")
    logger.error(f"❌ [请求验证] 请求体前1000字符: {body_str}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "message": "请求参数验证失败"}
    )

# 请求日志中间件（必须在其他中间件之前注册）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求"""
    import time
    start_time = time.time()
    
    # 记录请求信息（强制输出，确保日志可见）
    request_path = request.url.path
    request_method = request.method
    logger.info(f"📥 [请求] {request_method} {request_path}")
    
    if request.url.query:
        logger.debug(f"📥 [请求] 查询参数: {request.url.query}")
    
    # 对于POST/PUT请求，记录Content-Type和部分请求体
    if request_method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "")
        logger.info(f"📥 [请求] Content-Type: {content_type}")
        
        # 对于文件上传，记录文件名
        if "multipart/form-data" in content_type:
            logger.info(f"📥 [请求] 文件上传请求")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        status_code = response.status_code
        logger.info(f"📤 [响应] {request_method} {request_path} - {status_code} ({process_time:.3f}s)")
        
        # 如果状态码是错误码，记录详细信息
        if status_code >= 400:
            logger.warning(f"⚠️ [响应错误] {request_method} {request_path} - {status_code}")
        
        return response
    except Exception as e:
        import traceback
        process_time = time.time() - start_time
        error_trace = traceback.format_exc()
        logger.error(f"❌ [请求异常] {request_method} {request_path} - 异常: {str(e)} ({process_time:.3f}s)")
        logger.error(f"❌ [请求异常] 错误堆栈:\n{error_trace}")
        raise

# 配置CORS中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3003", "http://localhost:3004"],  # 前端开发服务器地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
# 将 data 目录挂载到 /static/data，用于访问上传的图片和生成的页面
app.mount("/static/data", StaticFiles(directory=settings.DATA_DIR), name="data")

# 注册路由
app.include_router(process.router, prefix="/api/process", tags=["智能处理"])
app.include_router(creation.router, prefix="/api/creation", tags=["创作管理"])
app.include_router(web_image.router, prefix="/api/web-images", tags=["网络图片管理"])
app.include_router(export.router, prefix="/api/export", tags=["文档导出"])
app.include_router(annotation.router, prefix="/api/creation", tags=["注释管理"])
app.include_router(node_documents.router, tags=["节点文档"])

# Agent API
app.include_router(agent.router, prefix="/api/agent", tags=["Agent对话"])

# Assistant API
app.include_router(assistant.router, prefix="/api/assistant", tags=["智能助手"])

# 工艺文档API
app.include_router(process_documents.router, tags=["工艺文档"])

# 任务记忆和上下文API
app.include_router(task_router, tags=["任务管理"])
app.include_router(document_router, tags=["文档上下文"])

# PDF解析状态API
app.include_router(pdf_status.router)

# DeepSeek API
app.include_router(deepseek.router, prefix="/api/deepseek", tags=["DeepSeek LLM"])

# 素材库 API（从文件系统读取）
app.include_router(materials.router, prefix="/api", tags=["素材库"])

# Context API
app.include_router(context.router, prefix="/api/context", tags=["context"])

# Draft API
app.include_router(draft.router, prefix="/api/drafts", tags=["初稿管理"])

# Profile API
app.include_router(profile.router, prefix="/api/profile", tags=["用户画像"])

# Frontend SPA mount moved to file end (after all @app routes) so /health and
# API routes match first; previously it sat here, intercepting /health -> 404.


# ============ 生产模式：后端直接 serve 前端构建产物（单端口）============
# Only active when frontend/dist exists. Dev mode has no dist -> vite:3000.
# Content-Type is declared explicitly via _media_type() to decouple from the
# Windows registry (which may map .html to a polluted value like "text/utf-8").
FRONTEND_DIST = settings.PROJECT_ROOT / "frontend" / "dist"


@app.get("/")
async def root():
    """根路径：生产模式(dist 存在)返回前端首页，开发模式返回API信息"""
    if FRONTEND_DIST.is_dir():
        return FileResponse(FRONTEND_DIST / "index.html", media_type="text/html; charset=utf-8")
    return {
        "name": "智能工艺文件辅助编辑系统",
        "version": "0.1.0",
        "status": "running",
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}


if FRONTEND_DIST.is_dir():
    logger.info(f"📦 前端静态托管已启用: {FRONTEND_DIST}")

    # SPA catch-all (registered LAST, after all /api routers + @app routes):
    # serve the file if it exists (explicit media_type), else index.html.
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate, media_type=_media_type(candidate))
        return FileResponse(FRONTEND_DIST / "index.html", media_type="text/html; charset=utf-8")
else:
    logger.info("📦 前端 dist 不存在，开发模式（前端走 vite dev server）")

if __name__ == "__main__":
    import uvicorn
    import logging
    
    # 配置 uvicorn 日志，避免覆盖我们的日志系统
    # 禁用 uvicorn 的默认日志处理器，使用我们的日志系统
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers = []
    
    # 启动服务器
    logger.info(f"🌐 服务器启动在 http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📝 日志级别: INFO")
    logger.info(f"🔄 自动重载: {'开启' if settings.DEBUG else '关闭'}")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        log_config=None,  # 禁用 uvicorn 的默认日志配置，使用我们的日志系统
        access_log=True,  # 启用访问日志（但会被我们的中间件覆盖）
    )




