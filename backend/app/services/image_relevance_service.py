"""
图片相关性评分服务
使用Qwen-VL评估图片与文章主题的相关性
"""
from typing import Dict, Optional, List
from pathlib import Path
import json

from app.services.vl_service import vl_service
from app.utils.logger import logger


class ImageRelevanceService:
    """图片相关性评分服务"""
    
    def __init__(self):
        """初始化服务"""
        self.vl = vl_service
    
    async def evaluate_relevance(
        self,
        image_path: Path,
        topic: str,
        context: Optional[str] = None,
        min_score: float = 0.5
    ) -> Dict:
        """
        评估图片与主题的相关性
        使用 Qwen-VL 的多模态能力进行内容理解，而不仅仅是 OCR。
        
        Args:
            image_path: 图片文件路径
            topic: 文章主题/标题
            context: 上下文内容（可选）
            min_score: 最低接受分数
        
        Returns:
            {
                "relevance_score": 0.85,  # 0-1分数
                "description": "图片内容描述",
                "is_relevant": True,  # 是否相关
                "reason": "评估理由",
                "recommendation": "使用建议"
            }
        """
        logger.info(f"🎨 评估图片相关性(VL模式): {image_path.name} vs '{topic}'")
        
        try:
            # 构建智能评估提示词
            query = f"""请分析这张图片，并评估它作为以下主题文章配图的相关性。
文章主题：{topic}
{f"上下文场景：{context}" if context else ""}

任务：
1. 描述图片中的核心视觉内容。
2. 给出相关性评分 (0-1分，1为完美匹配)。
3. 给出一个布尔值判断是否推荐使用。
4. 说明理由。

请务必只输出 JSON，不要有代码块标记：
{{
  "description": "...",
  "relevance_score": 0.0,
  "is_relevant": false,
  "reason": "..."
}}
"""
            # 调用 Qwen-VL 理解图片
            response_text = await self.vl.understand_image_content(image_path, query)
            
            # 尝试解析 JSON
            try:
                # 处理可能的代码块标记
                clean_json = response_text.strip()
                if clean_json.startswith("```"):
                    import re
                    match = re.search(r'\{.*\}', clean_json, re.DOTALL)
                    if match:
                        clean_json = match.group(0)
                
                result_data = json.loads(clean_json)
                
                # 填充默认值
                relevance_score = float(result_data.get("relevance_score", 0.5))
                is_relevant = bool(result_data.get("is_relevant", relevance_score >= min_score))
                
                result = {
                    "relevance_score": relevance_score,
                    "description": result_data.get("description", "图片内容"),
                    "is_relevant": is_relevant,
                    "reason": result_data.get("reason", "AI 综合评估"),
                    "recommendation": "建议使用" if is_relevant else "不建议使用"
                }
            except Exception as parse_e:
                logger.error(f"❌ 解析 VL 响应失败: {parse_e}")
                raise
                score = min(0.3 + len(matches) * 0.2, 1.0) if matches else 0.2
                
                result = {
                    "relevance_score": score,
                    "description": ocr_text[:100],
                    "is_relevant": score >= min_score,
                    "reason": f"关键词匹配: {len(matches)}个",
                    "recommendation": "建议审核"
                }
            
            logger.info(f"✅ 评估完成: 分数={result['relevance_score']:.2f}, 推荐={result['is_relevant']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 评估失败: {str(e)}")
            return {
                "relevance_score": 0.5,
                "description": "分析出错",
                "is_relevant": False,
                "reason": str(e),
                "recommendation": "建议人工审核"
            }
    
    async def batch_evaluate(
        self,
        image_paths: List[str],
        topic: str,
        context: Optional[str] = None,
        top_k: int = 1
    ) -> List[Dict]:
        """
        批量评估，选择最优的 K 张
        """
        logger.info(f"📊 批量评估 {len(image_paths)} 张图片...")
        
        results = []
        for path_str in image_paths:
            path = Path(path_str)
            if not path.exists(): continue
            
            eval_res = await self.evaluate_relevance(path, topic, context)
            results.append({
                "image_path": path_str,
                **eval_res
            })
            
        # 按分数排序
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:top_k]


# 全局实例
_image_relevance_service = None

def get_image_relevance_service() -> ImageRelevanceService:
    """获取图片相关性服务单例"""
    global _image_relevance_service
    if _image_relevance_service is None:
        _image_relevance_service = ImageRelevanceService()
    return _image_relevance_service
