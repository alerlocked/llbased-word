import json
from typing import List, Dict, Optional
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.shared.config import UNRELIABLE_DOMAINS

# 导入阿里云 V3 SDK (TEA)
from alibabacloud_iqs20241111.client import Client as IQSClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_iqs20241111 import models as iqs_models
from alibabacloud_tea_util import models as util_models


class AliyunSearchTool:
    """
    阿里云通用搜索工具 (IQS)
    使用 2024-11-11 版本 V3 SDK
    """
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self._init_client()
        
    def _init_client(self):
        try:
            if not self.config.ALIYUN_ACCESS_KEY_ID or not self.config.ALIYUN_ACCESS_KEY_SECRET:
                logger.warning("⚠️ 阿里云 AccessKey 未配置，搜索功能将受限")
                return

            # 配置 OpenApi
            openapi_config = open_api_models.Config(
                access_key_id=self.config.ALIYUN_ACCESS_KEY_ID,
                access_key_secret=self.config.ALIYUN_ACCESS_KEY_SECRET
            )
            # 设置 Endpoint
            openapi_config.endpoint = self.config.ALIYUN_IQS_ENDPOINT
            
            self.client = IQSClient(openapi_config)
            logger.info("✅ 阿里云 IQS V3 客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ 阿里云 IQS 客户端初始化失败: {str(e)}")
            self.client = None

    def _simplify_query(self, query: str) -> str:
        """简化查询，避免过长或包含无效字符导致搜索失败"""
        if not query:
            return ""
            
        # 移除多余的换行和空格
        simplified = query.replace('\n', ' ').strip()
        
        # 如果太长，尝试提取核心关键词
        if len(simplified) > 40:
            # 优先取第一个标点前的核心句
            for sep in ['。', '！', '？', '；', '，', '!', '?', ';', ',']:
                if sep in simplified:
                    parts = simplified.split(sep)
                    if len(parts[0]) > 5:
                        simplified = parts[0]
                        break
        
        # 截断到合理长度 (阿里云 IQS 通常建议查询词在 30 字符内)
        if len(simplified) > 30:
            simplified = simplified[:30]
            
        return simplified

    def search(self, query: str, max_results: int = 5) -> str:
        simplified_query = self._simplify_query(query)
        logger.info(f"🌐 阿里云网络搜索: {simplified_query}")
        
        if not self.client:
            return json.dumps({"status": "error", "error": "客户端未初始化", "results": []})
            
        try:
            request = iqs_models.GenericSearchRequest(query=simplified_query)
            
            # 使用更通用的调用方式
            try:
                response = self.client.generic_search(request)
            except AttributeError:
                # 如果没有直接的 generic_search，使用 with_options
                runtime = util_models.RuntimeOptions()
                response = self.client.generic_search_with_options(request, runtime)
            
            body = response.body
            formatted_results = []
            
            # 阿里云 IQS GenericSearch 返回 page_items 而非 data/results
            page_items = getattr(body, 'page_items', None) or []
            
            for item in page_items[:max_results]:
                item_dict = item.to_map() if hasattr(item, 'to_map') else item
                if not isinstance(item_dict, dict): 
                    continue
                    
                formatted_results.append({
                    "title": item_dict.get("title") or item_dict.get("Title") or "",
                    "snippet": item_dict.get("snippet") or item_dict.get("Snippet") or item_dict.get("description") or item_dict.get("display_link") or "",
                    "url": item_dict.get("link") or item_dict.get("Link") or item_dict.get("url") or "",
                    "source": "Aliyun IQS"
                })
                
            logger.info(f"✅ 阿里云搜索完成，找到 {len(formatted_results)} 条结果 (page_items: {len(page_items)})")
            return json.dumps({
                "status": "success",
                "query": simplified_query,
                "total_results": len(formatted_results),
                "results": formatted_results
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ 阿里云搜索执行失败: {str(e)}")
            return json.dumps({"status": "error", "error": str(e), "results": []}, ensure_ascii=False, indent=2)

    def search_images(self, query: str, max_results: int = 6) -> List[Dict]:
        """
        阿里云图片搜索 (通过 IQS 综合搜索结果提取)
        """
        simplified_query = self._simplify_query(query)
        logger.info(f"🔍 阿里云图片搜索: {simplified_query} (最多 {max_results} 张)")
        
        if not self.client:
            return []
            
        try:
            # 内部执行函数以支持递归/重试
            def _do_search(q):
                request = iqs_models.GenericSearchRequest(query=q)
                try:
                    return self.client.generic_search(request)
                except AttributeError:
                    runtime = util_models.RuntimeOptions()
                    return self.client.generic_search_with_options(request, runtime)

            response = _do_search(simplified_query)
            
            # #region agent log
            try:
                import time
                with open(r"d:\ai_idea\Journalist\.cursor\debug.log", "a", encoding="utf-8") as f:
                    import json
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "check_response_body_attrs",
                        "location": "aliyun_search.py:search_images",
                        "message": "Inspecting response body attributes",
                        "data": {
                            "has_data": hasattr(response.body, 'data'),
                            "has_results": hasattr(response.body, 'results'),
                            "dir_body": dir(response.body)
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception as e:
                pass
            # #endregion

            # 如果结果为空且查询词较长，尝试更短的关键词
            # FIX: Use getattr to safely access .data and .results
            has_data = getattr(response.body, 'data', None)
            has_results = getattr(response.body, 'results', None)
            
            if (not has_data and not has_results) and len(simplified_query) > 10:
                logger.warning(f"⚠️ 图片搜索无结果: {simplified_query}")

            body = response.body
            images = []
            
            # 阿里云 IQS GenericSearch 返回的结构：
            # - scene_items: 场景/图片结果（优先）
            # - page_items: 网页结果（包含缩略图）
            
            # 1. 先从 scene_items 提取图片
            scene_items = getattr(body, 'scene_items', None) or []
            if scene_items:
                for item in scene_items:
                    if len(images) >= max_results:
                        break
                    item_dict = item.to_map() if hasattr(item, 'to_map') else (item if isinstance(item, dict) else {})
                    # scene_items 中图片 URL 可能在多个字段（包括 imageLink）
                    image_url = (
                        item_dict.get('image_url') or 
                        item_dict.get('imageUrl') or 
                        item_dict.get('imageLink') or
                        item_dict.get('ImageUrl') or
                        item_dict.get('original_image_url') or
                        item_dict.get('main_pic_url') or
                        item_dict.get('img') or
                        item_dict.get('pic_url')
                    )
                    if image_url:
                        # 过滤低质量来源
                        url_lower = image_url.lower()
                        is_unreliable = any(domain in url_lower for domain in UNRELIABLE_DOMAINS)
                        
                        images.append({
                            "url": image_url,
                            "title": item_dict.get("title") or item_dict.get("Title") or "",
                            "source": "Aliyun IQS Scene",
                            "is_reliable": not is_unreliable
                        })
            
            # 2. 如果 scene_items 不够，从 page_items 提取缩略图
            page_items = getattr(body, 'page_items', None) or []
            if len(images) < max_results and page_items:
                # 调试：打印第一个 item 的 images 字段内容
                if page_items:
                    first_item = page_items[0]
                    first_dict = first_item.to_map() if hasattr(first_item, 'to_map') else first_item
                    images_field = first_dict.get('images') if isinstance(first_dict, dict) else None
                    if images_field:
                        # 处理 images 数组中的元素
                        if len(images_field) > 0:
                            first_img = images_field[0]
                            first_img_dict = first_img.to_map() if hasattr(first_img, 'to_map') else first_img
                            logger.info(f"📋 page_items[0].images[0] 内容: {first_img_dict}")
                    else:
                        logger.info(f"📋 page_items[0].images 为空或不存在")
                
                for item in page_items:
                    if len(images) >= max_results:
                        break
                    item_dict = item.to_map() if hasattr(item, 'to_map') else (item if isinstance(item, dict) else {})
                    
                    # 从 images 数组提取图片（这是主要来源）
                    images_arr = item_dict.get('images') or []
                    for img_item in images_arr:
                        if len(images) >= max_results:
                            break
                        # 处理 img_item，可能是对象需要 to_map
                        img_dict = img_item.to_map() if hasattr(img_item, 'to_map') else (img_item if isinstance(img_item, dict) else {})
                        
                        # 尝试多个可能的字段名（包括阿里云返回的 imageLink）
                        image_url = None
                        for key in ['url', 'src', 'imageUrl', 'image_url', 'imageLink', 'image_link',
                                    'originalImage', 'thumbnailUrl', 'thumbnail', 'Url', 'Source']:
                            val = img_dict.get(key) if isinstance(img_dict, dict) else None
                            if val and isinstance(val, str) and val.startswith('http'):
                                image_url = val
                                break
                        
                        # 如果 img_dict 本身就是字符串 URL
                        if not image_url and isinstance(img_item, str) and img_item.startswith('http'):
                            image_url = img_item
                        
                        if image_url:
                            # 过滤低质量来源
                            # 检查是否为不可靠来源
                            url_lower = image_url.lower()
                            is_unreliable = any(domain in url_lower for domain in UNRELIABLE_DOMAINS)
                            
                            # 优先添加可靠来源的图片
                            images.append({
                                "url": image_url,
                                "title": item_dict.get("title") or item_dict.get("Title") or "",
                                "source": "Aliyun IQS Page",
                                "is_reliable": not is_unreliable  # 标记可靠性
                            })
            
            # 按可靠性排序：可靠来源优先
            images.sort(key=lambda x: x.get('is_reliable', False), reverse=True)
            
            logger.info(f"✅ 阿里云图片搜索完成，找到 {len(images)} 张图片（可靠来源: {sum(1 for img in images if img.get('is_reliable', False))} 张）")
            
            # 调试：如果还是没有图片，记录详细信息
            if len(images) == 0:
                logger.warning(f"⚠️ 未找到图片，响应属性: scene_items={len(scene_items) if scene_items else 0}, page_items={len(page_items)}")
            
            return images
            
        except Exception as e:
            logger.error(f"❌ 阿里云图片搜索失败: {str(e)}")
            return []

def get_aliyun_search_tool(config):
    """获取阿里云搜索工具单例"""
    return AliyunSearchTool(config)
