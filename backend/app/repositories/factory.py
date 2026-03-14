"""
Repository工厂
根据配置创建相应的Repository实例
"""
from typing import Optional

from app.shared.logging import get_logger
from app.repositories.protocols import TaskMemoryRepository
from app.repositories.json_repository import JsonFileRepository

logger = get_logger(__name__)

# 延迟导入SQLite实现，避免部署前报错
_sqlite_repository = None


def _get_sqlite_repository():
    """延迟获取SQLite Repository类"""
    global _sqlite_repository
    if _sqlite_repository is None:
        try:
            from app.repositories.sqlite_repository import SQLiteRepository
            _sqlite_repository = SQLiteRepository
        except ImportError:
            pass
    return _sqlite_repository


def create_repository(
    repo_type: str = "json",
    **kwargs,
) -> TaskMemoryRepository:
    """
    创建Repository实例

    Args:
        repo_type: Repository类型，支持 "json" 或 "sqlite"
        **kwargs: 传递给Repository构造函数的参数

    Returns:
        Repository实例

    Raises:
        ValueError: 不支持的Repository类型
    """
    repo_type = repo_type.lower()

    if repo_type == "json":
        base_dir = kwargs.get("base_dir", "data/tasks")
        logger.info("creating_json_repository", base_dir=base_dir)
        return JsonFileRepository(base_dir=base_dir)

    elif repo_type == "sqlite":
        SQLiteRepository = _get_sqlite_repository()
        if SQLiteRepository is None:
            raise ValueError("SQLiteRepository不可用，请先完成实现")

        db_path = kwargs.get("db_path", "data/tasks.db")
        logger.info("creating_sqlite_repository", db_path=db_path)
        return SQLiteRepository(db_path=db_path)

    else:
        raise ValueError(f"不支持的Repository类型: {repo_type}，支持的类型: json, sqlite")


# 全局Repository实例（单例模式）
_repository_instance: Optional[TaskMemoryRepository] = None


def get_repository() -> TaskMemoryRepository:
    """
    获取全局Repository实例

    使用方式:
        from app.repositories.factory import get_repository
        repo = get_repository()
        task_id = repo.create_task("电缆装配编辑")

    Returns:
        Repository实例
    """
    global _repository_instance

    if _repository_instance is None:
        # 从配置读取
        from app.config import settings
        repo_type = getattr(settings, "REPOSITORY_TYPE", "json")

        if repo_type == "json":
            base_dir = str(getattr(settings, "TASK_DATA_DIR", "data/tasks"))
            _repository_instance = create_repository(repo_type="json", base_dir=base_dir)
        elif repo_type == "sqlite":
            db_path = str(getattr(settings, "SQLITE_DB_PATH", "data/tasks.db"))
            _repository_instance = create_repository(repo_type="sqlite", db_path=db_path)
        else:
            # 默认使用JSON
            _repository_instance = create_repository(repo_type="json")

        logger.info("repository_initialized", repo_type=repo_type)

    return _repository_instance


def reset_repository():
    """
    重置全局Repository实例

    用于测试或切换配置后重新初始化
    """
    global _repository_instance
    _repository_instance = None
    logger.info("repository_reset")
