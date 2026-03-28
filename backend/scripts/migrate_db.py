"""
数据库迁移脚本：素材库重构 - Task 1

删除 Material 表的 content, search_result_id 字段
删除 MaterialPage 表的 text_content, figures 字段

使用方法：
    cd backend
    python scripts/migrate_db.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from sqlalchemy import create_engine, text

from app.config import get_settings


def get_db_path() -> str:
    """获取数据库路径"""
    settings = get_settings()
    return settings.DATABASE_URL.replace("sqlite:///", "")


def backup_data(conn: sqlite3.Connection, backup_dir: Path):
    """备份要删除的数据到 JSON 文件"""
    print("📦 备份现有数据...")

    cursor = conn.cursor()

    # 备份 Material 的 content 和 search_result_id
    cursor.execute("SELECT id, content, search_result_id FROM materials")
    materials = cursor.fetchall()

    material_backup = []
    for row in materials:
        material_backup.append({
            "id": row[0],
            "content": row[1],
            "search_result_id": row[2]
        })

    # 备份 MaterialPage 的 text_content 和 figures
    cursor.execute("SELECT id, text_content, figures FROM material_pages")
    pages = cursor.fetchall()

    page_backup = []
    for row in pages:
        page_backup.append({
            "id": row[0],
            "text_content": row[1],
            "figures": row[2]
        })

    # 保存备份文件
    backup_file = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_data = {
        "backup_time": datetime.now().isoformat(),
        "materials": material_backup,
        "material_pages": page_backup
    }

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 备份完成: {backup_file}")
    print(f"   - Material 记录: {len(material_backup)}")
    print(f"   - MaterialPage 记录: {len(page_backup)}")

    return backup_file


def drop_columns(conn: sqlite3.Connection):
    """删除字段（SQLite 需要重建表）"""
    print("\n🔧 执行字段删除...")

    cursor = conn.cursor()

    # 1. 重建 materials 表
    print("   处理 materials 表...")

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='materials'")
    if cursor.fetchone():
        # 创建新表（不含删除的字段）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materials_new (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                material_type VARCHAR(20) NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)

        # 复制数据
        cursor.execute("""
            INSERT INTO materials_new (id, name, material_type, created_at, updated_at)
            SELECT id, name, material_type, created_at, updated_at FROM materials
        """)

        # 删除旧表，重命名新表
        cursor.execute("DROP TABLE materials")
        cursor.execute("ALTER TABLE materials_new RENAME TO materials")

        print("   ✅ materials 表已更新")

    # 2. 重建 material_pages 表
    print("   处理 material_pages 表...")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='material_pages'")
    if cursor.fetchone():
        # 创建新表（不含删除的字段）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS material_pages_new (
                id INTEGER PRIMARY KEY,
                material_id INTEGER NOT NULL,
                page_number INTEGER NOT NULL,
                image_path VARCHAR(512) NOT NULL,
                created_at DATETIME,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        """)

        # 复制数据
        cursor.execute("""
            INSERT INTO material_pages_new (id, material_id, page_number, image_path, created_at)
            SELECT id, material_id, page_number, image_path, created_at FROM material_pages
        """)

        # 删除旧表，重命名新表
        cursor.execute("DROP TABLE material_pages")
        cursor.execute("ALTER TABLE material_pages_new RENAME TO material_pages")

        print("   ✅ material_pages 表已更新")

    conn.commit()
    print("✅ 字段删除完成")


def verify_migration(conn: sqlite3.Connection):
    """验证迁移结果"""
    print("\n🔍 验证迁移结果...")

    cursor = conn.cursor()

    # 检查 materials 表结构
    cursor.execute("PRAGMA table_info(materials)")
    columns = [row[1] for row in cursor.fetchall()]
    expected_columns = ["id", "name", "material_type", "created_at", "updated_at"]

    if columns == expected_columns:
        print(f"   ✅ materials 表结构正确: {columns}")
    else:
        print(f"   ❌ materials 表结构错误!")
        print(f"      预期: {expected_columns}")
        print(f"      实际: {columns}")
        return False

    # 检查 material_pages 表结构
    cursor.execute("PRAGMA table_info(material_pages)")
    columns = [row[1] for row in cursor.fetchall()]
    expected_columns = ["id", "material_id", "page_number", "image_path", "created_at"]

    if columns == expected_columns:
        print(f"   ✅ material_pages 表结构正确: {columns}")
    else:
        print(f"   ❌ material_pages 表结构错误!")
        print(f"      预期: {expected_columns}")
        print(f"      实际: {columns}")
        return False

    return True


def main():
    print("=" * 50)
    print("素材库重构 - 数据库迁移")
    print("=" * 50)

    # 准备备份目录
    backup_dir = Path(__file__).parent.parent / "data" / "migrations"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 连接数据库
    db_path = get_db_path()
    print(f"\n📂 数据库路径: {db_path}")

    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在!")
        return

    conn = sqlite3.connect(db_path)

    try:
        # 1. 备份数据
        backup_file = backup_data(conn, backup_dir)

        # 2. 删除字段
        drop_columns(conn)

        # 3. 验证结果
        if verify_migration(conn):
            print("\n" + "=" * 50)
            print("✅ 迁移成功完成!")
            print(f"   备份文件: {backup_file}")
            print("=" * 50)
        else:
            print("\n❌ 迁移验证失败，请检查!")

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
