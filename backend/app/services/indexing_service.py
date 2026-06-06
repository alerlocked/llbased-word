"""
IndexingService - Document indexing for ChromaDB vector search

Reads VLM-parsed JSON documents from exports_vlm_full/ and indexes
tables and text blocks into ChromaDB for semantic retrieval.
Replaces the deprecated RAGSyncService for process document indexing.
"""
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.shared.logging import get_logger
from app.config import settings
from app.tools.vector_store import VectorStore

logger = get_logger(__name__)


class IndexingService:
    """
    Index VLM-parsed documents into ChromaDB for vector search.

    Reads structured JSON from exports_vlm_full/ and indexes each table
    and text block as a separate document with metadata for filtering.
    """

    CONTENT_LIST_SUFFIX = "_content_list_v2.json"
    VLM_SUBDIR = "vlm"

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or settings.EXPORTS_VLM_DIR
        self._documents_dir = settings.DOCUMENTS_DIR
        self._vector_store: Optional[VectorStore] = None

    @property
    def vector_store(self) -> VectorStore:
        """Lazy-init VectorStore with process_knowledge collection."""
        if self._vector_store is None:
            self._vector_store = VectorStore({"collection_name": "process_knowledge"})
        return self._vector_store

    async def index_document(self, doc_name: str) -> Dict[str, Any]:
        """
        Index a single document into ChromaDB.

        Searches both exports_vlm_full/ and documents/ dirs for the
        content_list_v2.json file.

        Args:
            doc_name: Document name (filename stem, e.g. "全单电缆装配规程")

        Returns:
            Indexing result with counts
        """
        content_path = self._resolve_content_list(doc_name)

        if not content_path:
            return {"success": False, "error": f"Content file not found for: {doc_name}"}

        try:
            with open(content_path, "r", encoding="utf-8") as f:
                pages = json.load(f)

            documents = []
            metadatas = []

            for page_idx, page in enumerate(pages):
                for item in page:
                    item_type = item.get("type", "")
                    content_data = item.get("content", {})

                    if item_type == "table":
                        table_html = content_data.get("html", "")
                        captions = content_data.get("table_caption", [])
                        caption_text = captions[0].get("content", "") if captions else ""
                        table_type = content_data.get("table_type", "unknown")

                        if not table_html.strip():
                            continue

                        # Use caption + html text as indexable content
                        text = f"{caption_text}\n{table_html}" if caption_text else table_html
                        doc_id = self._make_doc_id(doc_name, page_idx, "table", len(documents))

                        documents.append({"id": doc_id, "text": text})
                        metadatas.append({
                            "source": doc_name,
                            "page": page_idx + 1,
                            "item_type": "table",
                            "table_type": table_type,
                            "caption": caption_text,
                        })

                    elif item_type in ("text", "title", "header"):
                        text_content = content_data if isinstance(content_data, str) else content_data.get("text", "")
                        if not text_content or not text_content.strip():
                            continue

                        doc_id = self._make_doc_id(doc_name, page_idx, "text", len(documents))
                        documents.append({"id": doc_id, "text": text_content})
                        metadatas.append({
                            "source": doc_name,
                            "page": page_idx + 1,
                            "item_type": item_type,
                        })

            if not documents:
                return {"success": True, "indexed_count": 0, "message": "No indexable content found"}

            # Remove old entries for this document before re-indexing
            await self._remove_by_source(doc_name)

            # Index into ChromaDB
            result = await self.vector_store.add_documents(documents, metadatas)

            logger.info("document_indexed", doc_name=doc_name, count=len(documents))
            return {
                "success": result.get("success", True),
                "indexed_count": len(documents),
                "doc_name": doc_name,
            }

        except Exception as e:
            logger.error("document_indexing_failed", doc_name=doc_name, error=str(e))
            return {"success": False, "error": str(e)}

    async def index_all(self) -> Dict[str, Any]:
        """
        Index all documents from both exports_vlm_full/ and documents/ dirs.

        Returns:
            Summary of indexing results
        """
        results = []
        errors = []
        total_indexed = 0
        seen: set[str] = set()

        scan_dirs = []
        if self._data_dir.exists():
            scan_dirs.append(self._data_dir)
        if self._documents_dir.exists():
            scan_dirs.append(self._documents_dir)

        for base_dir in scan_dirs:
            for doc_dir in sorted(base_dir.iterdir()):
                if not doc_dir.is_dir():
                    continue
                vlm_dir = doc_dir / self.VLM_SUBDIR
                if not vlm_dir.exists():
                    continue

                content_files = list(vlm_dir.glob(f"*{self.CONTENT_LIST_SUFFIX}"))
                if not content_files:
                    continue

                doc_name = content_files[0].stem.replace(self.CONTENT_LIST_SUFFIX, "") or doc_dir.name
                if doc_name in seen:
                    continue
                seen.add(doc_name)

                result = await self.index_document(doc_name)
                if result.get("success"):
                    total_indexed += result.get("indexed_count", 0)
                    results.append(result)
                else:
                    errors.append({"doc_name": doc_name, "error": result.get("error")})

        logger.info("all_documents_indexed", total=total_indexed, errors=len(errors))
        return {
            "success": True,
            "total_indexed": total_indexed,
            "documents_processed": len(results),
            "errors": errors,
        }

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Semantic search across indexed documents.

        Args:
            query: Search query text
            top_k: Number of results
            filters: Metadata filters (source, item_type, etc.)

        Returns:
            Search results from VectorStore
        """
        return await self.vector_store.search(
            query=query,
            top_k=top_k,
            filters=filters,
        )

    async def get_indexed_sources(self) -> List[str]:
        """Get list of document sources currently indexed."""
        try:
            result = await self.vector_store.search_by_metadata(
                metadata_filters={},
                limit=1000,
            )
            sources = set()
            for item in result.get("results", []):
                meta = item.get("metadata", {})
                if "source" in meta:
                    sources.add(meta["source"])
            return sorted(sources)
        except Exception:
            return []

    async def _remove_by_source(self, doc_name: str) -> int:
        """Remove all entries for a given source document."""
        try:
            result = await self.vector_store.search_by_metadata(
                metadata_filters={"source": doc_name},
                limit=1000,
            )
            count = 0
            for item in result.get("results", []):
                await self.vector_store.delete_document(item["id"])
                count += 1
            return count
        except Exception:
            return 0

    def _make_doc_id(self, doc_name: str, page: int, item_type: str, index: int) -> str:
        """Generate deterministic document ID."""
        raw = f"{doc_name}:{page}:{item_type}:{index}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _resolve_content_list(self, doc_name: str) -> Optional[Path]:
        """Find content_list_v2.json across static and live doc dirs."""
        # 1. Static path
        static = self._data_dir / doc_name / self.VLM_SUBDIR / f"{doc_name}{self.CONTENT_LIST_SUFFIX}"
        if static.exists():
            return static

        # 2. Live upload pipeline path
        if self._documents_dir.exists():
            for doc_dir in self._documents_dir.iterdir():
                if not doc_dir.is_dir():
                    continue
                vlm_dir = doc_dir / self.VLM_SUBDIR
                if not vlm_dir.exists():
                    continue
                for f in vlm_dir.glob(f"*{self.CONTENT_LIST_SUFFIX}"):
                    if f.stem.replace(self.CONTENT_LIST_SUFFIX, "") == doc_name:
                        return f
                    if doc_dir.name == doc_name:
                        return f

        return None
