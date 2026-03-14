"""
WebSearchTool - 网络搜索工具
全面切换至阿里云 IQS，彻底替换 DuckDuckGo
"""
import json
import asyncio
from typing import List, Dict, Optional

from app.utils.logger import logger
from app.agents.tools.aliyun_search import AliyunSearchTool

class WebSearchTool:
    """
    网络搜索工具 - 全面切换至阿里云 IQS
    """
    
    def __init__(self, config):
        self.config = config
        self.aliyun_tool = AliyunSearchTool(config)
        self.image_search_tool = None
    
    def search(self, query: str, max_results: int = 5) -> str:
        """使用阿里云搜索接口"""
        return self.aliyun_tool.search(query, max_results)
    
    async def search_with_images(
        self,
        query: str,
        max_text_results: int = 5,
        max_images: int = 3,
        include_images: bool = True
    ) -> Dict:
        """
        综合搜索（文本+图片） - 全面使用阿里云
        """
        logger.info(f"🌐🖼️ 开始阿里云综合搜索: {query}")
        
        result = {
            "query": query,
            "text_results": [],
            "image_results": []
        }
        
        # 文本搜索
        text_search_result = self.search(query, max_text_results)
        try:
            text_data = json.loads(text_search_result)
            result["text_results"] = text_data.get("results", [])
        except:
            pass
        
        # 图片搜索
        if include_images and max_images > 0:
            try:
                from app.agents.tools.image_search import get_image_search_tool
                
                if self.image_search_tool is None:
                    self.image_search_tool = get_image_search_tool()
                
                # 异步搜索并下载图片 (内部已切换到阿里云)
                images = await self.image_search_tool.search_and_download(
                    query,
                    count=max_images,
                    safe_search=True
                )
                
                result["image_results"] = images
                logger.info(f"✅ 找到 {len(images)} 张相关图片")
                
            except Exception as e:
                logger.error(f"❌ 阿里云图片搜索失败: {str(e)}")
                result["image_results"] = []
        
        return result

