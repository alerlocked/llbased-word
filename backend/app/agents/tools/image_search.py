"""
图片搜索工具 - 整合本地图片库和网络图片搜索
支持：
1. 本地图片库语义搜索（通过 RAG + 多模态 Embedding）
2. 网络图片搜索（Bing API / 阿里云 IQS）
"""
from typing import List, Dict, Optional
from pathlib import Path
import aiohttp
import asyncio
from datetime import datetime
import json

from app.config import settings
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.shared.config import UNRELIABLE_DOMAINS
from app.utils.file_utils import calculate_file_hash


class ImageSearchTool:
    """
    综合图片搜索工具
    - 本地图片库：使用 ChromaDB 向量检索
    - 网络图片：使用 Bing Image Search API（优先）或阿里云 IQS
    """
    
    def __init__(self):
        """初始化图片搜索工具"""
        self.image_dir = settings.DATA_DIR / "web_images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.session = None
        
        # 阿里云搜索
        from app.agents.tools.aliyun_search import AliyunSearchTool
        self.aliyun_tool = AliyunSearchTool(settings)
        
        # Bing 图片搜索
        from app.agents.tools.bing_image_search import get_bing_image_search
        self.bing_search = get_bing_image_search()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self.session
    
    async def search_images(
        self,
        keyword: str,
        count: int = 5,
        safe_search: bool = True
    ) -> List[Dict]:
        """
        搜索网络图片（优先使用 Bing，备选阿里云）
        """
        logger.info(f"🔍 网络搜索图片: {keyword}, 数量: {count}")
        
        try:
            # 优先使用 Bing
            if self.bing_search.is_enabled:
                results = await self.bing_search.search(keyword, count, safe_search="Moderate" if safe_search else "Off")
                if results:
                    logger.info(f"✅ Bing 图片搜索完成，找到 {len(results)} 张")
                    return results
            
            # 备选：阿里云
            results = self.aliyun_tool.search_images(keyword, count)
            return results
            
        except Exception as e:
            logger.error(f"❌ 网络图片搜索失败: {str(e)}")
            return []
    
    async def search_local_images(
        self,
        query: str,
        project_id: Optional[int] = None,
        count: int = 10
    ) -> List[Dict]:
        """
        搜索本地图片库（通过 RAG 向量检索）
        
        Args:
            query: 搜索文本
            project_id: 项目ID（可选，用于过滤）
            count: 返回数量
            
        Returns:
            本地图片列表
        """
        logger.info(f"🔍 搜索本地图片库: {query}")
        
        try:
            from app.services.rag_sync_service import get_rag_sync_service
            rag_service = get_rag_sync_service()
            
            # 搜索用户上传的图片
            images = await rag_service.search_images(query, project_id, count)
            
            # 搜索文档中提取的图片
            figures = await rag_service.search_figures(query, project_id, count)
            
            # 合并结果
            all_local = []
            seen_paths = set()
            
            for img in images:
                path = img.get("image_path", "")
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    all_local.append({
                        "url": f"/static/{path}" if not path.startswith("/") else path,
                        "local_path": path,
                        "title": img.get("caption", ""),
                        "source": "local_upload",
                        "score": img.get("score", 0)
                    })
            
            for fig in figures:
                path = fig.get("file_path", "")
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    all_local.append({
                        "url": f"/static/{path}" if not path.startswith("/") else path,
                        "local_path": path,
                        "title": fig.get("caption", ""),
                        "source": "document_figure",
                        "score": fig.get("score", 0)
                    })
            
            # 按相关度排序
            all_local.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            logger.info(f"✅ 本地图片搜索完成，找到 {len(all_local)} 张")
            return all_local[:count]
            
        except Exception as e:
            logger.error(f"❌ 本地图片搜索失败: {str(e)}")
            return []
    
    async def unified_search(
        self,
        query: str,
        project_id: Optional[int] = None,
        local_count: int = 5,
        web_count: int = 5,
        prefer_local: bool = True
    ) -> Dict[str, List[Dict]]:
        """
        统一图片搜索：同时搜索本地和网络
        
        Args:
            query: 搜索文本
            project_id: 项目ID
            local_count: 本地图片数量
            web_count: 网络图片数量
            prefer_local: 优先本地（影响结果排序）
            
        Returns:
            {
                "local": [...],  # 本地图片
                "web": [...],    # 网络图片
                "combined": [...] # 合并结果
            }
        """
        logger.info(f"🔍 统一图片搜索: {query}")
        
        # 并行搜索本地和网络
        local_task = self.search_local_images(query, project_id, local_count)
        web_task = self.search_images(query, web_count)
        
        local_results, web_results = await asyncio.gather(
            local_task, web_task,
            return_exceptions=True
        )
        
        # 处理异常
        if isinstance(local_results, Exception):
            logger.warning(f"本地搜索异常: {local_results}")
            local_results = []
        if isinstance(web_results, Exception):
            logger.warning(f"网络搜索异常: {web_results}")
            web_results = []
        
        # 合并结果
        combined = []
        if prefer_local:
            combined.extend(local_results)
            combined.extend(web_results)
        else:
            combined.extend(web_results)
            combined.extend(local_results)
        
        logger.info(f"✅ 统一搜索完成: 本地 {len(local_results)} 张, 网络 {len(web_results)} 张")
        
        return {
            "local": local_results,
            "web": web_results,
            "combined": combined
        }
    
    def _is_reliable_source(self, url: str) -> bool:
        """
        判断图片源是否可靠（过滤不可靠来源）
        
        Args:
            url: 图片URL
        
        Returns:
            是否可靠
        """
        # 使用共享配置中的不可靠域名列表
        url_lower = url.lower()
        for domain in UNRELIABLE_DOMAINS:
            if domain in url_lower:
                return False
        
        # 优先使用知名图床和CDN
        reliable_domains = [
            'sinaimg.cn',
            'thepaper.cn',
            'china.cn',
            'sogoucdn.com',
            'baidu.com',
            'qq.com',
            '163.com',
            'sohu.com',
            'ifeng.com',
            'people.com.cn',
            'xinhuanet.com',
            'cctv.com',
        ]
        
        for domain in reliable_domains:
            if domain in url_lower:
                return True
        
        # 默认允许，但会在日志中标记
        return True
    
    async def download_image(
        self,
        url: str,
        keyword: str,
        title: Optional[str] = None,
        max_retries: int = 2
    ) -> Optional[Dict]:
        """
        下载图片到本地（带重试机制）
        
        Args:
            url: 图片URL
            keyword: 搜索关键词
            title: 图片标题
            max_retries: 最大重试次数
        
        Returns:
            下载结果信息，包含本地路径
        """
        logger.info(f"📥 开始下载图片: {url[:50]}...")
        
        # 检查来源可靠性
        if not self._is_reliable_source(url):
            logger.warning(f"⚠️ 图片来源可能不可靠: {url[:50]}...")
            # 仍然尝试下载，但记录警告
        
        # 重试机制
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                session = await self._get_session()
                
                # 下载图片（增加超时时间）
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                async with session.get(url, timeout=timeout, allow_redirects=True) as response:
                    if response.status != 200:
                        error_msg = f"HTTP状态码: {response.status}"
                        logger.warning(f"⚠️ 下载失败 ({attempt + 1}/{max_retries + 1}): {error_msg}")
                        if attempt < max_retries:
                            await asyncio.sleep(1)  # 等待1秒后重试
                            continue
                        return None
                    
                    image_data = await response.read()
                    
                    # 检查文件大小
                    if len(image_data) < 1024:  # 小于1KB，可能不是有效图片
                        logger.warning("⚠️ 文件太小，可能不是有效图片")
                        return None
                    
                    if len(image_data) > 10 * 1024 * 1024:  # 大于10MB
                        logger.warning("⚠️ 文件太大，超过10MB")
                        return None
                    
                    # 验证是否为有效图片（检查文件头）
                    valid_image_headers = [
                        b'\xff\xd8\xff',  # JPEG
                        b'\x89PNG\r\n\x1a\n',  # PNG
                        b'RIFF',  # WebP/GIF
                        b'GIF8',  # GIF
                    ]
                    is_valid = False
                    for header in valid_image_headers:
                        if image_data.startswith(header):
                            is_valid = True
                            break
                    
                    if not is_valid:
                        logger.warning("⚠️ 文件不是有效的图片格式")
                        return None
                    
                    # 计算文件哈希（用于去重）
                    file_hash = calculate_file_hash(image_data)
                    
                    # 检测文件类型
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        ext = '.jpg'
                    elif 'png' in content_type:
                        ext = '.png'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    elif 'gif' in content_type:
                        ext = '.gif'
                    else:
                        # 根据文件头判断
                        if image_data.startswith(b'\xff\xd8\xff'):
                            ext = '.jpg'
                        elif image_data.startswith(b'\x89PNG'):
                            ext = '.png'
                        elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
                            ext = '.webp'
                        elif image_data.startswith(b'GIF8'):
                            ext = '.gif'
                        else:
                            ext = '.jpg'  # 默认
                    
                    # 保存到本地
                    date_dir = self.image_dir / datetime.now().strftime("%Y%m%d")
                    date_dir.mkdir(parents=True, exist_ok=True)
                    
                    filename = f"{file_hash}{ext}"
                    local_path = date_dir / filename
                    
                    # 检查是否已存在
                    if local_path.exists():
                        logger.info(f"✓ 图片已存在: {filename}")
                        # 存储相对于 DATA_DIR 的路径（用于数据库）
                        relative_path = str(local_path.relative_to(settings.DATA_DIR))
                        return {
                            "local_path": relative_path,
                            "file_hash": file_hash,
                            "file_size": len(image_data),
                            "existed": True
                        }
                    
                    # 写入文件
                    with open(local_path, 'wb') as f:
                        f.write(image_data)
                    
                    logger.info(f"✅ 图片已保存: {filename} (大小: {len(image_data) / 1024:.1f}KB)")
                    
                    # 存储相对于 DATA_DIR 的路径（用于数据库）
                    relative_path = str(local_path.relative_to(settings.DATA_DIR))
                    return {
                        "local_path": relative_path,
                        "file_hash": file_hash,
                        "file_size": len(image_data),
                        "existed": False
                    }
                    
            except asyncio.TimeoutError:
                last_error = "连接超时"
                logger.warning(f"⏱️ 下载超时 ({attempt + 1}/{max_retries + 1}): {url[:50]}...")
                if attempt < max_retries:
                    await asyncio.sleep(2)  # 等待2秒后重试
                    continue
            except aiohttp.ClientError as e:
                last_error = f"网络错误: {str(e)}"
                logger.warning(f"🌐 网络错误 ({attempt + 1}/{max_retries + 1}): {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
            except Exception as e:
                last_error = f"未知错误: {str(e)}"
                logger.error(f"❌ 下载失败 ({attempt + 1}/{max_retries + 1}): {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
        
        # 所有重试都失败
        logger.error(f"❌ 图片下载最终失败: {url[:50]}... (错误: {last_error})")
        return None
    
    async def comprehensive_search(
        self,
        keywords: List[str],
        images_per_keyword: int = 2,
        safe_search: bool = True
    ) -> List[Dict]:
        """
        综合搜索：并行执行多个关键词搜索，汇总结果
        
        Args:
            keywords: 关键词列表
            images_per_keyword: 每个关键词下载数量
            
        Returns:
            汇总的图片列表（已去重）
        """
        logger.info(f"🔍📥 开始综合图片搜索，关键词组: {keywords}")
        
        tasks = []
        for kw in keywords:
            # 限制每个词的下载数量，保证速度
            tasks.append(self.search_and_download(kw, count=images_per_keyword, safe_search=safe_search))
            
        results_groups = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_images = []
        seen_hashes = set()
        
        for group in results_groups:
            if isinstance(group, list):
                for img in group:
                    # 简单去重
                    if img.get('file_hash') and img['file_hash'] not in seen_hashes:
                        seen_hashes.add(img['file_hash'])
                        all_images.append(img)
                        
        logger.info(f"✅ 综合搜索完成，共收集 {len(all_images)} 张候选图片")
        return all_images

    async def search_and_download(
        self,
        keyword: str,
        count: int = 3,
        safe_search: bool = True
    ) -> List[Dict]:
        """
        搜索并下载图片
        
        Args:
            keyword: 搜索关键词
            count: 下载数量
            safe_search: 安全搜索
        
        Returns:
            已下载的图片信息列表
        """
        logger.info(f"🔍📥 搜索并下载图片: {keyword}")
        
        # 搜索图片
        search_results = await self.search_images(keyword, count * 2, safe_search)  # 多搜索一些，以防下载失败
        
        if not search_results:
            logger.warning("⚠️ 未找到图片")
            return []
        
        # 并发下载图片
        download_tasks = []
        for result in search_results[:count * 2]:  # 尝试下载更多，以确保成功数量
            task = self.download_image(
                result['url'],
                keyword,
                result.get('title')
            )
            download_tasks.append((task, result))
        
        # 等待所有下载完成
        downloaded_images = []
        for task, result in download_tasks:
            download_result = await task
            if download_result:
                downloaded_images.append({
                    **result,
                    **download_result,
                    "keyword": keyword,
                    "download_time": datetime.now().isoformat()
                })
                
                if len(downloaded_images) >= count:
                    break
        
        logger.info(f"✅ 成功下载 {len(downloaded_images)}/{count} 张图片")
        return downloaded_images
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def __del__(self):
        """析构函数，确保会话关闭"""
        if self.session and not self.session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
                else:
                    loop.run_until_complete(self.session.close())
            except:
                pass


# 全局实例
_image_search_tool = None

def get_image_search_tool() -> ImageSearchTool:
    """获取图片搜索工具单例"""
    global _image_search_tool
    if _image_search_tool is None:
        _image_search_tool = ImageSearchTool()
    return _image_search_tool

