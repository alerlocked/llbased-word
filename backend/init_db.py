# -*- coding: utf-8 -*-
"""
数据库初始化脚本
运行此脚本来创建数据库表
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from app.database import init_db
from app.utils.logger import logger

if __name__ == "__main__":
    logger.info("开始初始化数据库...")
    init_db()
    logger.info("数据库初始化完成！")




