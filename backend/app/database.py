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
    echo=settings.SQL_ECHO,  # decoupled from DEBUG (DEBUG also gates uvicorn reload)
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _migrate_db():
    """Run lightweight auto-migrations for new columns/tables."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)

    # Create material_folders table if missing
    if "material_folders" not in insp.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE material_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL,
                    parent_id INTEGER,
                    sort_order INTEGER DEFAULT 0,
                    created_at DATETIME,
                    FOREIGN KEY(parent_id) REFERENCES material_folders(id)
                )
            """))
        logger.info("✅ Auto-migration: created material_folders table")

    # Add folder_id column to materials if missing
    material_cols = {c["name"] for c in insp.get_columns("materials")}
    if "folder_id" not in material_cols:
        with engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE materials ADD COLUMN folder_id INTEGER
                REFERENCES material_folders(id)
            """))
        logger.info("✅ Auto-migration: added folder_id to materials")

    # Index material_catalog.standard_code for G18a catalog enrich exact lookup (P1-1)
    if "material_catalog" in insp.get_table_names():
        idx_names = {i["name"] for i in insp.get_indexes("material_catalog")}
        if "idx_material_catalog_standard_code" not in idx_names:
            with engine.begin() as conn:
                conn.execute(text(
                    "CREATE INDEX idx_material_catalog_standard_code "
                    "ON material_catalog(standard_code)"
                ))
            logger.info("✅ Auto-migration: added index on material_catalog.standard_code")
        # Add tech_params column for auxiliary material technical parameters
        # (力矩/固化/温度 etc.) — 辅料牌号自带参数, in-context 先行 (2a), 结构化下沉 (2b)
        mc_cols = {c["name"] for c in insp.get_columns("material_catalog")}
        if "tech_params" not in mc_cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE material_catalog ADD COLUMN tech_params TEXT"
                ))
            logger.info("✅ Auto-migration: added tech_params to material_catalog")


def init_db():
    """初始化数据库，创建所有表"""
    logger.info("📊 初始化数据库...")
    Base.metadata.create_all(bind=engine)
    _migrate_db()
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







