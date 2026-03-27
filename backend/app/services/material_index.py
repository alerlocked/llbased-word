"""
MaterialIndexService - 素材索引服务
自动生成素材库的 manifest.json 索引文件

"""
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.utils.logger import logger


from app.config import settings


from app.utils.file_utils import calculate_file_hash


from app.database import SessionLocal
from app.models.database import Material

from sqlalchemy.orm import Session


from app.database import get_db


from app.utils.logger import log_workflow


import uuid


import asyncio
import aiofiles


from concurrent.futures import ThreadPoolExecutor


import threading
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import os
import json
import hashlib
import shutil


from app.database import get_db, SessionLocal
from app.models.database import Material, CreationProject
from app.utils.logger import logger, log_workflow
from app.config import settings
from app.utils.file_utils import calculate_file_hash
from app.utils.db_utils import get_or_404


from app.utils.path_utils import build_static_url

# ==================== 数据模型 ====================

class MaterialManifest(BaseModel):
    """素材索引清单"""
    version: str = "1.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    root_path: str
    project_id: Optional[int] = None
    files: List[dict] = Field(default_factory=list)
    directories: List[dict] = Field(default_factory=list)
    total_size: int = 0
    total_files: int = 0
    file_types: Dict[str, int] = Field(default_factory=dict)

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True

class MaterialIndexService:
    """素材索引服务"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)

    def generate_manifest(
        self,
        folder_path: str,
        project_id: Optional[int] = None
    ) -> MaterialManifest:
        """
        生成文件夹索引

        Args:
            folder_path: 文件夹路径
            project_id: 项目ID（可选）
        Returns:
            MaterialManifest: 索引清单
        """
        logger.info(f"[索引服务] 开始生成索引: {folder_path}")

        files = []
        directories = set()
        total_size = 0
        file_types: Dict[str, int] = {}

        # 遍历文件夹
        for root, dirs, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, folder_path)

                # 跳过隐藏文件和系统文件
                if filename.startswith('.') or filename.startswith('~'):
                    continue

                # 跳过临时文件
                if filename.endswith('.tmp') or filename.endswith('.temp'):
                    continue

                try:
                    # 获取文件信息
                    file_stat = os.stat(filepath)
                    file_ext = os.path.splitext(filename)[1].lower()

                    # 计算文件哈希（对于小文件)
                    file_hash = ""
                    if file_stat.st_size < 10 * 1024 * 1024:  # 小于10MB的文件计算哈希
                        file_hash = self._calculate_file_hash(filepath)

                    files.append({
                        "path": rel_path,
                        "name": filename,
                        "size": file_stat.st_size,
                        "type": file_ext,
                        "hash": file_hash,
                        "modified_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    })

                    # 统计文件类型
                    if file_ext:
                        file_types[file_ext] = file_types.get(file_ext, 0) + 1

                    # 统计总大小
                    total_size += file_stat.st_size

                    # 记录目录
                    dir_path = os.path.dirname(rel_path)
                    if dir_path:
                        directories.add(dir_path)

                except Exception as e:
                    logger.warning(f"[索引服务] 无法访问文件 {filepath}: {e}")

        # 构建目录信息
        dir_list = []
        for d in directories:
            dir_list.append({
                "path": d,
                "depth": d.count(os.sep),
                "file_count": self._count_files_in_dir(folder_path, d)
            })

        manifest = MaterialManifest(
            root_path=folder_path,
            project_id=project_id,
            files=files,
            directories=dir_list,
            total_size=total_size,
            total_files=len(files),
            file_types=file_types
        )

        logger.info(f"[索引服务] 索引生成完成: {len(files)} 个文件, {len(dir_list)} 个目录")

        return manifest

    def _calculate_file_hash(self, filepath: str) -> str:
        """计算文件 SHA256"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return f"sha256:{sha256.hexdigest()}"
        except Exception as e:
            logger.warning(f"[索引服务] 计算哈希失败 {filepath}: {e}")
            return ""

    def _count_files_in_dir(self, root_path: str, dir_path: str) -> int:
        """统计目录中的文件数量"""
        full_path = os.path.join(root_path, dir_path)
        if not os.path.isdir(full_path):
            return 0

        count = 0
        for _ in os.listdir(full_path):
            count += 1
        return count

    def save_manifest(
        self,
        manifest: MaterialManifest,
        output_path: Optional[str] = None
    ) -> str:
        """
        保存索引清单到文件

        Args:
            manifest: 索引清单
            output_path: 输出路径（可选，默认为文件夹下的 manifest.json）
        Returns:
            str: 保存的文件路径
        """
        if output_path is None:
            output_path = os.path.join(manifest.root_path, "manifest.json")

        # 保存到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(manifest.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info(f"[索引服务] 索引已保存: {output_path}")

        return output_path

    async def generate_and_save_manifest(
        self,
        folder_path: str,
        project_id: Optional[int] = None,
        output_path: Optional[str] = None
    ) -> tuple[MaterialManifest, str]:
        """
        异步生成并保存索引清单

        Args:
            folder_path: 文件夹路径
            project_id: 项目ID
            output_path: 输出路径
        Returns:
            tuple[MaterialManifest, str]: 索引清单和保存路径
        """
        loop = asyncio.get_event_loop()

        # 在线程池中执行IO密集操作
        manifest = await loop.run_in_executor(
            self.executor,
            self.generate_manifest,
            folder_path,
            project_id
        )

        # 保存索引
        saved_path = self.save_manifest(manifest, output_path)

        return manifest, saved_path


# 创建全局服务实例
material_index_service = MaterialIndexService()


