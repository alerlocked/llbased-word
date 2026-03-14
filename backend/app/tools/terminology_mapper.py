"""
工艺文件辅助编辑系统 - 术语映射工具
实现工艺术语的映射、匹配和标准化
"""
from typing import Dict, Any, Optional, List, Union
import json
import os
from pathlib import Path
from difflib import SequenceMatcher

from app.shared.logging import get_logger

logger = get_logger(__name__)


class TerminologyMapper:
    """
    术语映射工具

    负责工艺术语的标准化映射，
    支持精确匹配、模糊匹配和上下文感知的术语推荐
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化术语映射工具

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.terminology_dir = self.config.get("terminology_dir", "backend/data/terminology")
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.8)

        # 加载术语库
        self.terminology_data = self._load_terminology_data()
        self.supported_standards = list(self.terminology_data.keys())

        logger.info(
            "terminology_mapper_initialized",
            standards=self.supported_standards,
            terminology_dir=self.terminology_dir
        )

    def _load_terminology_data(self) -> Dict[str, Any]:
        """
        加载术语数据

        Returns:
            术语数据字典
        """
        terminology_data = {}

        try:
            terminology_path = Path(self.terminology_dir)
            if not terminology_path.exists():
                logger.warning("terminology_directory_not_found", path=self.terminology_dir)
                return terminology_data

            # 查找所有标准术语文件
            for standard_file in terminology_path.glob("*.json"):
                standard_name = standard_file.stem
                try:
                    with open(standard_file, 'r', encoding='utf-8') as f:
                        terminology_data[standard_name] = json.load(f)
                    logger.debug("terminology_standard_loaded", standard=standard_name)
                except Exception as e:
                    logger.error("failed_to_load_terminology_standard", standard=standard_name, error=str(e))

            if not terminology_data:
                logger.warning("no_terminology_standards_found", path=self.terminology_dir)

        except Exception as e:
            logger.error("terminology_loading_failed", error=str(e))

        return terminology_data

    async def map_terms(
        self,
        source_text: str,
        target_standard: str = "enterprise_standard",
        context: Optional[Dict[str, Any]] = None,
        fuzzy_matching: bool = True,
        confidence_threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        映射术语

        Args:
            source_text: 源文本
            target_standard: 目标标准
            context: 上下文
            fuzzy_matching: 是否启用模糊匹配
            confidence_threshold: 置信度阈值

        Returns:
            映射结果
        """
        try:
            if target_standard not in self.terminology_data:
                return {
                    "success": False,
                    "error": f"不支持的术语标准: {target_standard}",
                    "error_code": "UNSUPPORTED_STANDARD"
                }

            # 获取目标标准术语库
            standard_terms = self.terminology_data[target_standard]

            # 提取源文本中的术语
            extracted_terms = await self._extract_terms_from_text(source_text, context)

            mappings = []
            mapped_text = source_text

            for term_info in extracted_terms:
                term = term_info["term"]
                position = term_info["position"]

                # 查找精确匹配
                exact_match = await self._find_exact_match(term, standard_terms)
                if exact_match:
                    mapping = {
                        "source_term": term,
                        "target_term": exact_match["term"],
                        "confidence": 1.0,
                        "match_type": "exact",
                        "definition": exact_match.get("definition", ""),
                        "category": exact_match.get("category", ""),
                        "position": position
                    }
                    mappings.append(mapping)
                    # 替换文本中的术语
                    mapped_text = mapped_text[:position] + exact_match["term"] + mapped_text[position + len(term):]
                elif fuzzy_matching:
                    # 查找模糊匹配
                    fuzzy_match = await self._find_fuzzy_match(term, standard_terms, confidence_threshold)
                    if fuzzy_match:
                        mapping = {
                            "source_term": term,
                            "target_term": fuzzy_match["term"],
                            "confidence": fuzzy_match["confidence"],
                            "match_type": "fuzzy",
                            "definition": fuzzy_match.get("definition", ""),
                            "category": fuzzy_match.get("category", ""),
                            "position": position
                        }
                        mappings.append(mapping)
                        # 替换文本中的术语
                        mapped_text = mapped_text[:position] + fuzzy_match["term"] + mapped_text[position + len(term):]

            return {
                "success": True,
                "mapped_text": mapped_text,
                "mappings": mappings,
                "unmapped_terms": [t["term"] for t in extracted_terms if not any(m["source_term"] == t["term"] for m in mappings)]
            }

        except Exception as e:
            logger.error("term_mapping_failed", error=str(e), target_standard=target_standard)
            return {
                "success": False,
                "error": f"术语映射失败: {str(e)}",
                "error_code": "MAPPING_EXCEPTION"
            }

    async def _extract_terms_from_text(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        从文本中提取术语

        Args:
            text: 文本
            context: 上下文

        Returns:
            术语信息列表
        """
        # 这里应该实现更复杂的术语提取逻辑
        # 目前返回简单的分词结果作为占位符
        terms = []

        # 简单的中文分词（实际应用中应使用专业分词工具）
        words = text.split()
        position = 0

        for word in words:
            if len(word) > 1:  # 忽略单字符
                terms.append({
                    "term": word,
                    "position": position,
                    "length": len(word)
                })
            position += len(word) + 1  # +1 for space

        return terms

    async def _find_exact_match(self, term: str, standard_terms: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        查找精确匹配

        Args:
            term: 术语
            standard_terms: 标准术语库

        Returns:
            匹配结果
        """
        # 在标准术语库中查找精确匹配
        for category, terms in standard_terms.items():
            if isinstance(terms, dict):
                for std_term, term_info in terms.items():
                    if std_term == term or term_info.get("alias") == term:
                        return {
                            "term": std_term,
                            "definition": term_info.get("definition", ""),
                            "category": category,
                            "alias": term_info.get("alias", [])
                        }
            elif isinstance(terms, list):
                for term_item in terms:
                    if isinstance(term_item, dict):
                        if term_item.get("term") == term:
                            return {
                                "term": term_item.get("term"),
                                "definition": term_item.get("definition", ""),
                                "category": category,
                                "alias": term_item.get("alias", [])
                            }

        return None

    async def _find_fuzzy_match(self, term: str, standard_terms: Dict[str, Any], threshold: float) -> Optional[Dict[str, Any]]:
        """
        查找模糊匹配

        Args:
            term: 术语
            standard_terms: 标准术语库
            threshold: 相似度阈值

        Returns:
            最佳匹配结果
        """
        best_match = None
        best_score = 0.0

        # 遍历所有标准术语
        for category, terms in standard_terms.items():
            if isinstance(terms, dict):
                for std_term, term_info in terms.items():
                    score = self._calculate_similarity(term, std_term)
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = {
                            "term": std_term,
                            "definition": term_info.get("definition", ""),
                            "category": category,
                            "confidence": score,
                            "alias": term_info.get("alias", [])
                        }

                    # 检查别名
                    aliases = term_info.get("alias", [])
                    if isinstance(aliases, list):
                        for alias in aliases:
                            score = self._calculate_similarity(term, alias)
                            if score > best_score and score >= threshold:
                                best_score = score
                                best_match = {
                                    "term": std_term,
                                    "definition": term_info.get("definition", ""),
                                    "category": category,
                                    "confidence": score,
                                    "alias": aliases
                                }
            elif isinstance(terms, list):
                for term_item in terms:
                    if isinstance(term_item, dict):
                        std_term = term_item.get("term", "")
                        score = self._calculate_similarity(term, std_term)
                        if score > best_score and score >= threshold:
                            best_score = score
                            best_match = {
                                "term": std_term,
                                "definition": term_item.get("definition", ""),
                                "category": category,
                                "confidence": score,
                                "alias": term_item.get("alias", [])
                            }

        return best_match

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        计算字符串相似度

        Args:
            str1: 字符串1
            str2: 字符串2

        Returns:
            相似度分数 (0-1)
        """
        if not str1 or not str2:
            return 0.0

        return SequenceMatcher(None, str1, str2).ratio()

    async def find_similar_terms(self, term: str, target_standard: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        查找相似术语

        Args:
            term: 术语
            target_standard: 目标标准
            max_results: 最大结果数

        Returns:
            相似术语列表
        """
        if target_standard not in self.terminology_data:
            return []

        standard_terms = self.terminology_data[target_standard]
        similar_terms = []

        # 计算所有术语的相似度
        for category, terms in standard_terms.items():
            if isinstance(terms, dict):
                for std_term, term_info in terms.items():
                    similarity = self._calculate_similarity(term, std_term)
                    if similarity > self.similarity_threshold:
                        similar_terms.append({
                            "term": std_term,
                            "similarity": similarity,
                            "confidence": similarity,
                            "definition": term_info.get("definition", ""),
                            "category": category
                        })
            elif isinstance(terms, list):
                for term_item in terms:
                    if isinstance(term_item, dict):
                        std_term = term_item.get("term", "")
                        similarity = self._calculate_similarity(term, std_term)
                        if similarity > self.similarity_threshold:
                            similar_terms.append({
                                "term": std_term,
                                "similarity": similarity,
                                "confidence": similarity,
                                "definition": term_item.get("definition", ""),
                                "category": category
                            })

        # 按相似度排序并返回前N个结果
        similar_terms.sort(key=lambda x: x["similarity"], reverse=True)
        return similar_terms[:max_results]

    async def get_related_terms_by_category(self, category: str, target_standard: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        根据类别获取相关术语

        Args:
            category: 类别
            target_standard: 目标标准
            limit: 限制数量

        Returns:
            相关术语列表
        """
        if target_standard not in self.terminology_data:
            return []

        standard_terms = self.terminology_data[target_standard]
        related_terms = []

        if category in standard_terms:
            terms = standard_terms[category]
            if isinstance(terms, dict):
                for term, term_info in list(terms.items())[:limit]:
                    related_terms.append({
                        "term": term,
                        "definition": term_info.get("definition", ""),
                        "category": category,
                        "confidence": 0.9
                    })
            elif isinstance(terms, list):
                for term_item in terms[:limit]:
                    if isinstance(term_item, dict):
                        related_terms.append({
                            "term": term_item.get("term", ""),
                            "definition": term_item.get("definition", ""),
                            "category": category,
                            "confidence": 0.9
                        })

        return related_terms

    async def get_supported_standards(self) -> List[str]:
        """
        获取支持的术语标准

        Returns:
            支持的标准列表
        """
        return self.supported_standards

    async def get_term_definition(self, term: str, standard: str) -> Optional[str]:
        """
        获取术语定义

        Args:
            term: 术语
            standard: 标准

        Returns:
            术语定义
        """
        if standard not in self.terminology_data:
            return None

        standard_terms = self.terminology_data[standard]

        for category, terms in standard_terms.items():
            if isinstance(terms, dict) and term in terms:
                return terms[term].get("definition", "")
            elif isinstance(terms, list):
                for term_item in terms:
                    if isinstance(term_item, dict) and term_item.get("term") == term:
                        return term_item.get("definition", "")

        return None

    async def add_term_to_standard(self, term: str, definition: str, category: str, standard: str, alias: List[str] = None) -> Dict[str, Any]:
        """
        添加术语到标准

        Args:
            term: 术语
            definition: 定义
            category: 类别
            standard: 标准
            alias: 别名列表

        Returns:
            添加结果
        """
        try:
            if standard not in self.terminology_data:
                self.terminology_data[standard] = {}

            if category not in self.terminology_data[standard]:
                self.terminology_data[standard][category] = {}

            self.terminology_data[standard][category][term] = {
                "definition": definition,
                "alias": alias or [],
                "category": category,
                "added_at": "timestamp_placeholder"
            }

            # 保存到文件
            await self._save_terminology_data(standard)

            logger.info("term_added_to_standard", term=term, standard=standard, category=category)
            return {
                "success": True,
                "message": f"术语 '{term}' 已添加到标准 '{standard}'"
            }

        except Exception as e:
            logger.error("term_addition_failed", error=str(e), term=term, standard=standard)
            return {
                "success": False,
                "error": f"术语添加失败: {str(e)}",
                "error_code": "TERM_ADDITION_EXCEPTION"
            }

    async def _save_terminology_data(self, standard: str):
        """
        保存术语数据到文件

        Args:
            standard: 标准名称
        """
        try:
            terminology_path = Path(self.terminology_dir)
            terminology_path.mkdir(parents=True, exist_ok=True)

            standard_file = terminology_path / f"{standard}.json"
            with open(standard_file, 'w', encoding='utf-8') as f:
                json.dump(self.terminology_data[standard], f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error("terminology_saving_failed", error=str(e), standard=standard)