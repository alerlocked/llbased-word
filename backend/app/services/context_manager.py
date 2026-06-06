"""
文件系统上下文管理器
从exports_vlm_full读取PDF解析结果，构建LLM上下文
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.shared.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


@dataclass
class TableInfo:
    """表格信息"""
    page: int
    caption: str
    html: str
    table_type: str
    image_path: str


@dataclass
class DocumentInfo:
    """文档信息"""
    name: str
    path: Path
    table_count: int
    page_count: int


class ContextManager:
    """
    文件系统上下文管理器

    从exports_vlm_full目录读取VLM解析后的PDF文档，
    提供文档列表、表格获取、Markdown转换等功能。

    目录结构:
    data/exports_vlm_full/
    ├── 全单电缆装配规程/
    │   └── vlm/
    │       ├── 全单电缆装配规程_content_list_v2.json
    │       └── images/
    ├── extraction_summary.json
    └── html_tables/
    """

    CONTENT_LIST_SUFFIX = "_content_list_v2.json"
    PROCESSED_MD_SUFFIX = "_processed.md"
    VLM_SUBDIR = "vlm"
    IMAGES_SUBDIR = "images"

    def __init__(self, data_dir: str = None):
        """
        初始化ContextManager

        Args:
            data_dir: exports_vlm_full目录路径（默认使用项目根目录下的data/exports_vlm_full）
        """
        if data_dir is None:
            data_dir = str(settings.EXPORTS_VLM_DIR)
        self.data_dir = Path(data_dir)
        # Also scan live upload pipeline output: data/documents/*/vlm/
        self._documents_dir = settings.DOCUMENTS_DIR
        self._document_cache: Dict[str, List[Any]] = {}
        self._summary_cache: Optional[Dict[str, Any]] = None

        logger.info("context_manager_initialized", data_dir=str(self.data_dir))

    def get_document_list(self) -> List[DocumentInfo]:
        """
        获取已解析文档列表

        Scans both the static exports_vlm_full/ and the live upload
        pipeline output (data/documents/*/vlm/) directories.

        Returns:
            文档信息列表
        """
        documents = []
        seen_names: set[str] = set()

        scan_dirs = [self.data_dir]
        if self._documents_dir.exists():
            scan_dirs.append(self._documents_dir)

        for base_dir in scan_dirs:
            for doc_dir in base_dir.iterdir():
                if not doc_dir.is_dir():
                    continue

                vlm_dir = doc_dir / self.VLM_SUBDIR
                if not vlm_dir.exists():
                    continue

                content_files = list(vlm_dir.glob(f"*{self.CONTENT_LIST_SUFFIX}"))
                if not content_files:
                    continue

                # Use material name from JSON filename for live docs
                doc_name = content_files[0].stem.replace(self.CONTENT_LIST_SUFFIX, "")
                if not doc_name:
                    doc_name = doc_dir.name

                if doc_name in seen_names:
                    continue
                seen_names.add(doc_name)

                content_path = content_files[0]
                try:
                    with open(content_path, "r", encoding="utf-8") as f:
                        pages = json.load(f)

                    table_count = 0
                    page_count = len(pages)
                    for page in pages:
                        for item in page:
                            if item.get("type") == "table":
                                table_count += 1

                    documents.append(DocumentInfo(
                        name=doc_name,
                        path=doc_dir,
                        table_count=table_count,
                        page_count=page_count,
                    ))

                except Exception as e:
                    logger.warning("document_load_failed", doc_name=doc_name, error=str(e))

        logger.info("document_list_loaded", count=len(documents))
        return documents

    def get_document_tables(self, doc_name: str) -> List[TableInfo]:
        """
        获取文档的所有表格

        Args:
            doc_name: 文档名称

        Returns:
            表格信息列表
        """
        content = self._load_document_content(doc_name)
        if not content:
            return []

        tables = []
        for page_idx, page in enumerate(content):
            for item in page:
                if item.get("type") != "table":
                    continue

                table_content = item.get("content", {})
                captions = table_content.get("table_caption", [])
                caption_text = captions[0].get("content", "") if captions else ""

                image_source = table_content.get("image_source", {})
                image_path = image_source.get("path", "")

                tables.append(TableInfo(
                    page=page_idx + 1,
                    caption=caption_text.strip(),
                    html=table_content.get("html", ""),
                    table_type=table_content.get("table_type", "unknown"),
                    image_path=image_path,
                ))

        logger.info("tables_loaded", doc_name=doc_name, count=len(tables))
        return tables

    def get_document_markdown(self, doc_name: str) -> str:
        """
        获取文档的Markdown表示

        Args:
            doc_name: 文档名称

        Returns:
            Markdown格式的文档内容
        """
        # 优先使用预处理过的Markdown文件
        doc_dir = self.data_dir / doc_name
        processed_md = doc_dir / f"{doc_name}{self.PROCESSED_MD_SUFFIX}"

        if processed_md.exists():
            try:
                return processed_md.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("markdown_read_failed", path=str(processed_md), error=str(e))

        # 否则从JSON转换
        return self._convert_to_markdown(doc_name)

    def search_by_caption(self, doc_name: str, caption: str) -> List[TableInfo]:
        """
        按表格标题搜索

        Args:
            doc_name: 文档名称
            caption: 标题关键词（如 G4a, G5a）

        Returns:
            匹配的表格列表
        """
        tables = self.get_document_tables(doc_name)
        caption_upper = caption.upper()

        matched = [
            t for t in tables
            if caption_upper in t.caption.upper()
        ]

        logger.info(
            "caption_search",
            doc_name=doc_name,
            caption=caption,
            matched_count=len(matched),
        )

        return matched

    def build_document_context(
        self,
        doc_names: List[str],
        include_html: bool = False,
        max_tables: int = 50,
    ) -> str:
        """
        构建多文档上下文

        Args:
            doc_names: 文档名称列表
            include_html: 是否包含HTML表格
            max_tables: 最大表格数量限制

        Returns:
            格式化的上下文字符串
        """
        parts = []
        total_tables = 0

        for doc_name in doc_names:
            tables = self.get_document_tables(doc_name)

            parts.append(f"\n# 文档: {doc_name}")
            parts.append(f"表格数量: {len(tables)}")

            for table in tables:
                if total_tables >= max_tables:
                    parts.append(f"\n... 省略剩余表格（已达上限 {max_tables}）")
                    break

                parts.append(f"\n## 第{table.page}页 - {table.caption or '(无标题)'}")

                if include_html and table.html:
                    # 简化HTML，只保留文本内容
                    text = self._html_to_text(table.html)
                    parts.append(text[:500])  # 限制长度
                else:
                    parts.append(f"[表格类型: {table.table_type}]")

                total_tables += 1

            if total_tables >= max_tables:
                break

        context = "\n".join(parts)
        logger.info(
            "document_context_built",
            doc_count=len(doc_names),
            total_tables=total_tables,
            context_length=len(context),
        )

        return context

    def get_extraction_summary(self) -> Dict[str, Any]:
        """
        获取解析摘要信息

        Returns:
            摘要信息字典
        """
        if self._summary_cache is not None:
            return self._summary_cache

        summary_path = self.data_dir / "extraction_summary.json"
        if not summary_path.exists():
            return {}

        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                self._summary_cache = json.load(f)
            return self._summary_cache
        except Exception as e:
            logger.warning("summary_load_failed", error=str(e))
            return {}

    def _load_document_content(self, doc_name: str) -> Optional[List[List[Dict]]]:
        """
        加载文档内容（带缓存）

        Searches both static exports_vlm_full/ and live documents/ dirs.
        """
        if doc_name in self._document_cache:
            return self._document_cache[doc_name]

        content_path = self._resolve_content_list_path(doc_name)

        if not content_path:
            logger.warning("document_content_not_found", doc_name=doc_name)
            return None

        try:
            with open(content_path, "r", encoding="utf-8") as f:
                content = json.load(f)

            self._document_cache[doc_name] = content
            return content
        except Exception as e:
            logger.error("document_content_load_failed", doc_name=doc_name, error=str(e))
            return None

    def _resolve_content_list_path(self, doc_name: str) -> Optional[Path]:
        """Find content_list_v2.json across both static and live dirs."""
        # 1. Static path: exports_vlm_full/{doc_name}/vlm/{doc_name}_content_list_v2.json
        static_path = self.data_dir / doc_name / self.VLM_SUBDIR / f"{doc_name}{self.CONTENT_LIST_SUFFIX}"
        if static_path.exists():
            return static_path

        # 2. Live path: scan documents/*/vlm/ for matching content_list
        if self._documents_dir.exists():
            for doc_dir in self._documents_dir.iterdir():
                if not doc_dir.is_dir():
                    continue
                vlm_dir = doc_dir / self.VLM_SUBDIR
                if not vlm_dir.exists():
                    continue
                for f in vlm_dir.glob(f"*{self.CONTENT_LIST_SUFFIX}"):
                    # Match by doc_name in filename
                    if f.stem.replace(self.CONTENT_LIST_SUFFIX, "") == doc_name:
                        return f
                    # Fallback: match by directory name (material_id)
                    if doc_dir.name == doc_name:
                        return f

        return None

    def _convert_to_markdown(self, doc_name: str) -> str:
        """
        将JSON内容转换为Markdown格式
        """
        content = self._load_document_content(doc_name)
        if not content:
            return f"# 文档不存在: {doc_name}"

        parts = [f"# {doc_name}"]

        for page_idx, page in enumerate(content):
            parts.append(f"\n## 第{page_idx + 1}页\n")

            for item in page:
                item_type = item.get("type")

                if item_type == "table":
                    table_content = item.get("content", {})
                    captions = table_content.get("table_caption", [])
                    if captions:
                        caption_text = captions[0].get("content", "")
                        parts.append(f"### {caption_text}")

                    # 简化处理：只标注表格存在
                    parts.append(f"[{table_content.get('table_type', '表格')}]")

                elif item_type in ("page_header", "page_footer", "page_number"):
                    # 忽略页眉页脚
                    pass

        return "\n".join(parts)

    def _html_to_text(self, html: str) -> str:
        """
        简化HTML为纯文本
        """
        import re
        # 移除标签
        text = re.sub(r"<[^>]+>", " ", html)
        # 合并空白
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def clear_cache(self):
        """清除缓存"""
        self._document_cache.clear()
        self._summary_cache = None
        logger.info("context_manager_cache_cleared")
