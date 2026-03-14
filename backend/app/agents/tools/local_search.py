"""
LocalSearchTool - 本地素材搜索工具
从本地文档库检索相关素材
"""
from sqlalchemy.orm import Session
import json
from typing import List, Dict

from app.database import SessionLocal
from app.models.database import Material, CreationProject
from app.utils.logger import logger


class LocalSearchTool:
    """
    本地素材搜索工具 - 从文档库中检索相关内容
    支持关键词匹配
    """

    def __init__(self, config):
        """
        初始化本地搜索工具

        Args:
            config: 配置对象
        """
        self.config = config

    def search(self, keywords: str, project_id: int = None) -> str:
        """
        搜索本地素材

        Args:
            keywords: 关键词（JSON数组字符串或单个关键词）
            project_id: 项目ID（用于过滤）

        Returns:
            搜索结果（JSON格式字符串）
        """
        logger.info(f"🔍 开始本地素材搜索: {keywords} (项目ID: {project_id})")

        try:
            # 解析关键词
            try:
                keyword_list = json.loads(keywords)
                if not isinstance(keyword_list, list):
                    keyword_list = [str(keywords)]
            except:
                keyword_list = [str(keywords)]

            logger.info(f"📝 关键词列表: {keyword_list}")

            # 创建数据库会话
            db = SessionLocal()

            try:
                # 查询素材
                query = db.query(Material)

                # 如果指定了项目ID，过滤该项目的素材
                if project_id:
                    project = db.query(CreationProject).filter(CreationProject.id == project_id).first()
                    if project and project.material_ids:
                        query = query.filter(Material.id.in_(project.material_ids))

                materials = query.all()

                logger.info(f"📊 找到{len(materials)}个{'当前项目' if project_id else '全局'}素材")

                # 搜索相关内容
                results = []

                for material in materials:
                    if not material.content:
                        continue

                    # 搜索匹配的内容
                    matched_segments = []
                    content = material.content

                    # 检查是否包含任何关键词
                    for keyword in keyword_list:
                        if keyword and keyword.lower() in content.lower():
                            # 找到匹配位置附近的文本
                            idx = content.lower().find(keyword.lower())
                            start = max(0, idx - 50)
                            end = min(len(content), idx + len(keyword) + 100)
                            matched_text = content[start:end]

                            matched_segments.append({
                                "text": matched_text,
                                "matched_keyword": keyword,
                                "position": idx
                            })

                    # 如果有匹配的片段，添加到结果
                    if matched_segments:
                        results.append({
                            "material_id": material.id,
                            "material_name": material.name,
                            "material_type": material.material_type,
                            "matched_segments": matched_segments[:10],  # 最多返回10个片段
                            "total_matches": len(matched_segments)
                        })

                logger.info(f"✅ 搜索完成，找到{len(results)}个相关素材")

                # 返回JSON格式结果
                result_json = {
                    "status": "success",
                    "query": keyword_list,
                    "total_results": len(results),
                    "results": results[:5]  # 最多返回5个素材
                }

                return json.dumps(result_json, ensure_ascii=False, indent=2)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"❌ 本地素材搜索失败: {str(e)}")
            error_result = {
                "status": "error",
                "error": str(e),
                "results": []
            }
            return json.dumps(error_result, ensure_ascii=False, indent=2)

