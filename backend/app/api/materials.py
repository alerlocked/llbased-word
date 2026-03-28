# -*- coding: utf-8 -*-
"""
素材库 API 路由
从文件系统读取素材数据，不依赖数据库内容
"""
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Optional
import json

from app.config import settings
from app.utils.logger import logger

router = APIRouter()


def get_materials_dir() -> Path:
    """获取素材目录路径"""
    return Path(settings.DATA_DIR) / "materials"


def find_material_dir(material_id: int) -> Optional[Path]:
    """
    根据 material_id 查找素材目录

    Args:
        material_id: 素材ID

    Returns:
        素材目录路径，不存在则返回 None
    """
    materials_dir = get_materials_dir()
    if not materials_dir.exists():
        return None

    # 查找匹配的目录：{material_id}_*
    for dir_path in materials_dir.iterdir():
        if dir_path.is_dir() and dir_path.name.startswith(f"{material_id}_"):
            return dir_path

    return None


@router.get("/materials/{material_id}/summary")
async def get_material_summary(material_id: int):
    """
    返回素材索引（用于检索）

    从 data/materials/{material_id}_*/summary.json 读取

    Args:
        material_id: 素材ID

    Returns:
        素材的 summary.json 内容
    """
    logger.info(f"📖 获取素材索引: material_id={material_id}")

    try:
        material_dir = find_material_dir(material_id)
        if not material_dir:
            logger.warning(f"⚠️ 素材目录不存在: material_id={material_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"素材不存在: ID={material_id}"
            )

        summary_path = material_dir / "summary.json"
        if not summary_path.exists():
            logger.warning(f"⚠️ 索引文件不存在: {summary_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"索引文件不存在"
            )

        with open(summary_path, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)

        logger.info(f"✅ 索引获取成功: material_id={material_id}, 总页数={summary_data.get('total_pages', 0)}")

        return summary_data

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"❌ 索引文件格式错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"索引文件格式错误"
        )
    except Exception as e:
        logger.error(f"❌ 获取素材索引失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取索引失败: {str(e)}"
        )


@router.get("/materials/{material_id}/pages/{page_num}")
async def get_page_content(material_id: int, page_num: int):
    """
    返回具体页面内容（用于上下文注入）

    从 summary.json 获取页面信息，返回图片路径等

    Args:
        material_id: 素材ID
        page_num: 页码（从1开始）

    Returns:
        页面信息：标题、摘要、关键词、图片路径
    """
    logger.info(f"📖 获取页面内容: material_id={material_id}, page={page_num}")

    try:
        # 验证页码
        if page_num < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="页码必须大于0"
            )

        material_dir = find_material_dir(material_id)
        if not material_dir:
            logger.warning(f"⚠️ 素材目录不存在: material_id={material_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"素材不存在: ID={material_id}"
            )

        summary_path = material_dir / "summary.json"
        if not summary_path.exists():
            logger.warning(f"⚠️ 索引文件不存在: {summary_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"索引文件不存在"
            )

        # 读取索引
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)

        total_pages = summary.get("total_pages", 0)
        if page_num > total_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"页码超出范围: 最大页数为 {total_pages}"
            )

        # 获取页面信息
        pages = summary.get("pages", [])
        if page_num > len(pages):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"页面信息不存在"
            )

        page_info = pages[page_num - 1]

        # 构建图片路径
        # 图片位于 data/documents/{material_id}/vlm/images/material_{material_id}_page_{page_num}.png
        # 静态文件挂载在 /static/data
        image_path = f"/static/data/documents/{material_id}/vlm/images/material_{material_id}_page_{page_num}.png"

        result = {
            "material_id": material_id,
            "page_number": page_num,
            "title": page_info.get("title", f"第{page_num}页"),
            "summary": page_info.get("summary", ""),
            "keywords": page_info.get("keywords", []),
            "type": page_info.get("type", "text"),
            "tokens_estimate": page_info.get("tokens_estimate", 0),
            "tables": page_info.get("tables", []),
            "figures": page_info.get("figures", []),
            "image_path": image_path
        }

        logger.info(f"✅ 页面内容获取成功: material_id={material_id}, page={page_num}")

        return result

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"❌ 索引文件格式错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"索引文件格式错误"
        )
    except Exception as e:
        logger.error(f"❌ 获取页面内容失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取页面内容失败: {str(e)}"
        )


@router.get("/materials")
async def list_materials():
    """
    列出所有素材

    从 data/materials/index.json 读取素材列表

    Returns:
        素材列表
    """
    logger.info("📖 获取素材列表")

    try:
        index_path = get_materials_dir() / "index.json"
        if not index_path.exists():
            logger.warning("⚠️ 素材索引不存在")
            return {"materials": []}

        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)

        materials = index_data.get("materials", [])
        logger.info(f"✅ 获取素材列表: {len(materials)} 个")

        return {"materials": materials}

    except json.JSONDecodeError as e:
        logger.error(f"❌ 素材索引格式错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"素材索引格式错误"
        )
    except Exception as e:
        logger.error(f"❌ 获取素材列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取素材列表失败: {str(e)}"
        )


@router.get("/materials/{material_id}")
async def get_material_info(material_id: int):
    """
    获取素材基本信息

    从 index.json 和 manifest.json 读取

    Args:
        material_id: 素材ID

    Returns:
        素材基本信息
    """
    logger.info(f"📖 获取素材信息: material_id={material_id}")

    try:
        material_dir = find_material_dir(material_id)
        if not material_dir:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"素材不存在: ID={material_id}"
            )

        # 读取 manifest.json
        manifest_path = material_dir / "manifest.json"
        manifest_data = {}
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

        # 读取 summary.json 获取页数
        summary_path = material_dir / "summary.json"
        total_pages = 0
        if summary_path.exists():
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
                total_pages = summary_data.get("total_pages", 0)

        result = {
            "id": material_id,
            "name": material_dir.name.split('_', 1)[1] if '_' in material_dir.name else material_dir.name,
            "path": str(material_dir.relative_to(get_materials_dir())),
            "total_pages": total_pages,
            "manifest": manifest_data
        }

        logger.info(f"✅ 素材信息获取成功: material_id={material_id}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取素材信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取素材信息失败: {str(e)}"
        )
