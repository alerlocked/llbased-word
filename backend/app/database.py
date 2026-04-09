"""
数据库连接和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models.database import Base
from app.shared.logging import get_logger
logger = get_logger(__name__)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite需要此参数
    echo=settings.DEBUG,  # 开发模式下打印SQL语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """初始化数据库，创建所有表"""
    logger.info("📊 初始化数据库...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库初始化完成")

def get_db():
    """
    获取数据库会话（依赖注入）
    用于FastAPI路由中
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()







