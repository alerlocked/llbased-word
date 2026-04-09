"""
Bing Image Search API
作为网络图片搜索的备选方案
"""
import os
import httpx
from typing import List, Dict, Optional
from app.shared.logging import get_logger
logger = get_logger(__name__)


class BingImageSearch:
    """
    Bing 图片搜索
    使用 Bing Search API v7
    
    需要配置环境变量:
    - BING_SEARCH_API_KEY: Bing Search API 密钥
    """
    
    ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/search"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化
        
        Args:
            api_key: Bing Search API 密钥，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv("BING_SEARCH_API_KEY", "")
        self._enabled = bool(self.api_key)
        
        if not self._enabled:
            logger.warning("⚠️ Bing Image Search API 未配置 (缺少 BING_SEARCH_API_KEY)")
    
    @property
    def is_enabled(self) -> bool:
        """是否已配置并可用"""
        return self._enabled
    
    async def search(
        self,
        query: str,
        count: int = 10,
        safe_search: str = "Moderate",
        image_type: str = "Photo"
    ) -> List[Dict]:
        """
        搜索网络图片
        
        Args:
            query: 搜索关键词
            count: 返回数量 (最大 150)
            safe_search: 安全搜索级别 (Off, Moderate, Strict)
            image_type: 图片类型 (Photo, Clipart, Line, Face, etc.)
            
        Returns:
            图片列表，每个包含 url, thumbnail, title, source
        """
        if not self._enabled:
            logger.warning("⚠️ Bing Image Search 未启用")
            return []
        
        logger.info(f"🔍 Bing 图片搜索: {query} (count={count})")
        
        try:
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key
            }
            
            params = {
                "q": query,
                "count": min(count, 150),
                "safeSearch": safe_search,
                "imageType": image_type,
                "mkt": "zh-CN"  # 中国市场
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    self.ENDPOINT,
                    headers=headers,
                    params=params
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ Bing API 错误: {response.status_code} - {response.text}")
                    return []
                
                data = response.json()
                
            images = []
            for item in data.get("value", []):
                images.append({
                    "url": item.get("contentUrl", ""),
                    "thumbnail": item.get("thumbnailUrl", ""),
                    "title": item.get("name", ""),
                    "source": item.get("hostPageDisplayUrl", ""),
                    "width": item.get("width", 0),
                    "height": item.get("height", 0)
                })
            
            logger.info(f"✅ Bing 图片搜索完成，找到 {len(images)} 张")
            return images
            
        except Exception as e:
            logger.error(f"❌ Bing 图片搜索失败: {e}")
            return []
    
    def search_sync(
        self,
        query: str,
        count: int = 10,
        safe_search: str = "Moderate"
    ) -> List[Dict]:
        """
        同步版本的图片搜索
        """
        if not self._enabled:
            return []
        
        import requests
        
        logger.info(f"🔍 Bing 图片搜索 (同步): {query}")
        
        try:
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key
            }
            
            params = {
                "q": query,
                "count": min(count, 150),
                "safeSearch": safe_search,
                "mkt": "zh-CN"
            }
            
            response = requests.get(
                self.ENDPOINT,
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Bing API 错误: {response.status_code}")
                return []
            
            data = response.json()
            
            images = []
            for item in data.get("value", []):
                images.append({
                    "url": item.get("contentUrl", ""),
                    "thumbnail": item.get("thumbnailUrl", ""),
                    "title": item.get("name", ""),
                    "source": item.get("hostPageDisplayUrl", "")
                })
            
            logger.info(f"✅ Bing 图片搜索完成，找到 {len(images)} 张")
            return images
            
        except Exception as e:
            logger.error(f"❌ Bing 图片搜索失败: {e}")
            return []


# 单例
_bing_search_instance = None

def get_bing_image_search() -> BingImageSearch:
    """获取 Bing 图片搜索单例"""
    global _bing_search_instance
    if _bing_search_instance is None:
        _bing_search_instance = BingImageSearch()
    return _bing_search_instance

