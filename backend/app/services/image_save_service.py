"""
图片保存服务
在保存项目内容时，自动下载并保存所有网络图片和data URL
"""
import re
import base64
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
import aiohttp
from io import BytesIO
from PIL import Image

from app.config import settings
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.utils.file_utils import calculate_file_hash
from sqlalchemy.orm import Session
from app.models.database import WebImage


class ImageInfo:
    """图片信息"""
    def __init__(self, url: str, alt: str, start_pos: int, end_pos: int):
        self.url = url
        self.alt = alt
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.local_path: Optional[str] = None
        self.error: Optional[str] = None


class ImageSaveService:
    """图片保存服务"""
    
    def __init__(self):
        """初始化服务"""
        self.project_images_dir = settings.PROJECT_IMAGES_DIR
        self.project_images_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_image_urls(self, markdown: str) -> List[ImageInfo]:
        """
        从Markdown中提取所有图片URL
        
        Args:
            markdown: Markdown内容
            
        Returns:
            图片信息列表
        """
        images: List[ImageInfo] = []
        
        # 预处理：合并跨行的图片语法
        processed_markdown = re.sub(
            r'!\[([^\]]*)\]\s*[\r\n]+\s*\(([^)]+)\)',
            r'![\1](\2)',
            markdown
        )
        
        # 匹配所有图片语法：![alt](url)
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        for match in re.finditer(pattern, processed_markdown):
            alt = match.group(1) or '图片'
            url = match.group(2).strip()
            
            # 移除可能的引号
            url = url.strip('"\'')
            
            images.append(ImageInfo(
                url=url,
                alt=alt,
                start_pos=match.start(),
                end_pos=match.end()
            ))
        
        return images
    
    async def download_network_image(
        self,
        url: str,
        project_id: int,
        db: Session
    ) -> Optional[str]:
        """
        下载网络图片到本地
        
        Args:
            url: 图片URL
            project_id: 项目ID
            db: 数据库会话
            
        Returns:
            本地路径（相对于DATA_DIR），如果失败返回None
        """
        try:
            # 检查是否已下载
            existing = db.query(WebImage).filter(
                WebImage.original_url == url
            ).first()
            
            if existing and existing.local_path:
                # 验证文件是否存在
                file_path = settings.DATA_DIR / existing.local_path
                if file_path.exists():
                    logger.info(f"✅ 图片已存在，复用: {existing.local_path}")
                    return existing.local_path
            
            # 使用现有的图片搜索工具下载
            from app.agents.tools.image_search import get_image_search_tool
            image_tool = get_image_search_tool()
            
            download_result = await image_tool.download_image(
                url,
                f"项目{project_id}保存",
                None
            )
            
            if download_result and download_result.get('local_path'):
                logger.info(f"✅ 图片下载成功: {download_result['local_path']}")
                return download_result['local_path']
            else:
                logger.warning(f"⚠️ 图片下载失败: {url[:50]}...")
                return None
                
        except Exception as e:
            logger.error(f"❌ 下载网络图片失败: {url[:50]}..., 错误: {str(e)}")
            return None
    
    def save_data_url_image(
        self,
        data_url: str,
        project_id: int
    ) -> Optional[str]:
        """
        保存data URL图片到本地
        
        Args:
            data_url: data URL（格式：data:image/png;base64,...）
            project_id: 项目ID
            
        Returns:
            本地路径（相对于DATA_DIR），如果失败返回None
        """
        try:
            # 解析data URL
            if not data_url.startswith('data:image/'):
                logger.warning(f"⚠️ 无效的data URL格式: {data_url[:50]}...")
                return None
            
            # 提取MIME类型和base64数据
            header, encoded = data_url.split(',', 1)
            mime_type = header.split(';')[0].replace('data:', '')
            
            # 确定文件扩展名
            ext_map = {
                'image/png': '.png',
                'image/jpeg': '.jpg',
                'image/jpg': '.jpg',
                'image/gif': '.gif',
                'image/webp': '.webp',
                'image/svg+xml': '.svg'
            }
            ext = ext_map.get(mime_type, '.png')
            
            # 解码base64
            try:
                image_data = base64.b64decode(encoded)
            except Exception as e:
                logger.error(f"❌ base64解码失败: {str(e)}")
                return None
            
            # 计算文件哈希
            file_hash = calculate_file_hash(image_data)
            
            # 创建项目图片目录
            project_dir = self.project_images_dir / str(project_id)
            date_str = datetime.now().strftime("%Y%m%d")
            date_dir = project_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            file_name = f"{file_hash}{ext}"
            file_path = date_dir / file_name
            relative_path = f"project_images/{project_id}/{date_str}/{file_name}"
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(image_data)
            
            logger.info(f"✅ data URL图片保存成功: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"❌ 保存data URL图片失败: {str(e)}")
            return None
    
    def verify_local_path(self, path: str) -> bool:
        """
        验证本地路径是否存在
        
        Args:
            path: 相对路径（相对于DATA_DIR）
            
        Returns:
            文件是否存在
        """
        if not path:
            return False
        
        # 移除 /static/data/ 前缀（如果有）
        if path.startswith('/static/data/'):
            path = path.replace('/static/data/', '')
        elif path.startswith('/static/'):
            path = path.replace('/static/', '')
        elif path.startswith('static/data/'):
            path = path.replace('static/data/', '')
        
        file_path = settings.DATA_DIR / path
        return file_path.exists()
    
    async def process_project_images(
        self,
        markdown: str,
        project_id: int,
        db: Session
    ) -> str:
        """
        处理项目内容中的所有图片，下载并替换URL
        
        Args:
            markdown: Markdown内容
            project_id: 项目ID
            db: 数据库会话
            
        Returns:
            更新后的Markdown内容
        """
        # 提取所有图片URL
        images = self.extract_image_urls(markdown)
        
        if not images:
            logger.info(f"📝 项目{project_id}内容中无图片，跳过处理")
            return markdown
        
        logger.info(f"📝 项目{project_id}内容中发现{len(images)}张图片，开始处理...")
        
        # 从后往前替换，避免位置偏移问题
        result_markdown = markdown
        processed_count = 0
        failed_count = 0
        
        for img_info in reversed(images):
            url = img_info.url
            new_url = None
            
            # 判断URL类型
            if url.startswith('http://') or url.startswith('https://'):
                # 网络URL：下载到本地
                local_path = await self.download_network_image(url, project_id, db)
                if local_path:
                    new_url = f"/static/data/{local_path}"
                    processed_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"⚠️ 图片下载失败，保持原URL: {url[:50]}...")
                    continue
                    
            elif url.startswith('data:image/'):
                # data URL：解码并保存
                local_path = self.save_data_url_image(url, project_id)
                if local_path:
                    new_url = f"/static/data/{local_path}"
                    processed_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"⚠️ data URL保存失败，跳过: {url[:50]}...")
                    continue
                    
            elif url.startswith('/static/data/') or url.startswith('static/data/'):
                # 本地路径：验证文件是否存在
                # 移除前缀，获取相对路径
                relative_path = url.replace('/static/data/', '').replace('static/data/', '')
                if self.verify_local_path(relative_path):
                    # 文件存在，保持原URL
                    continue
                else:
                    # 文件不存在，记录警告
                    logger.warning(f"⚠️ 本地图片文件不存在: {relative_path}")
                    failed_count += 1
                    continue
            else:
                # 其他格式（可能是相对路径），尝试验证
                if self.verify_local_path(url):
                    # 确保使用正确的路径格式
                    if not url.startswith('/static/data/'):
                        new_url = f"/static/data/{url}" if not url.startswith('/') else f"/static/data{url}"
                        # 替换URL
                        old_markdown = f"![{img_info.alt}]({url})"
                        new_markdown = f"![{img_info.alt}]({new_url})"
                        result_markdown = result_markdown.replace(old_markdown, new_markdown)
                    continue
                else:
                    logger.warning(f"⚠️ 无法识别的图片URL格式: {url[:50]}...")
                    failed_count += 1
                    continue
            
            # 替换URL
            if new_url:
                old_markdown = f"![{img_info.alt}]({url})"
                new_markdown = f"![{img_info.alt}]({new_url})"
                result_markdown = result_markdown.replace(old_markdown, new_markdown)
        
        logger.info(f"✅ 图片处理完成: 成功{processed_count}张，失败{failed_count}张")
        return result_markdown


# 全局服务实例
_image_save_service: Optional[ImageSaveService] = None


def get_image_save_service() -> ImageSaveService:
    """获取图片保存服务实例"""
    global _image_save_service
    if _image_save_service is None:
        _image_save_service = ImageSaveService()
    return _image_save_service

