"""
文件系统服务 - 实现类似Manus的文件系统监听和上下文集成
"""
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent
import json
import hashlib
from datetime import datetime

from app.shared.logging import get_logger, timer, bind_context
# 导入pdf_table_extractor失败，模块不存在，已改用process_document_extractor
from app.tools.process_document_extractor import extract_process_document

logger = get_logger(__name__)


class FileSystemEventProcessor(FileSystemEventHandler):
    """文件系统事件处理器"""

    def __init__(self, callback: Callable, watch_patterns: List[str]):
        self.callback = callback
        self.watch_patterns = watch_patterns

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            asyncio.create_task(self.callback('created', event.src_path))

    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            asyncio.create_task(self.callback('modified', event.src_path))

    def on_deleted(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            asyncio.create_task(self.callback('deleted', event.src_path))

    def _should_process(self, file_path: str) -> bool:
        """判断是否应该处理该文件"""
        path = Path(file_path)

        # 检查文件扩展名
        for pattern in self.watch_patterns:
            if path.match(pattern):
                return True

        return False


class FileSystemService:
    """
    文件系统服务 - Manus风格的文件系统管理

    功能：
    1. 监听指定目录的文件变化
    2. 自动处理新文件（特别是PDF工艺文件）
    3. 将文件内容集成到AI上下文中
    4. 维护文件索引和元数据
    """

    def __init__(self, base_path: str = "./workspace"):
        self.base_path = Path(base_path)
        self.observer = None
        self.is_running = False

        # 配置监听模式
        self.watch_patterns = [
            "*.pdf",      # PDF工艺文件
            "*.docx",     # Word工艺文件
            "*.xlsx",     # Excel工艺文件
            "*.txt",      # 文本文件
            "*.md"        # Markdown文件
        ]

        # 文件索引
        self.file_index = {}
        self.index_file = self.base_path / ".file_index.json"

        # 加载现有索引
        self._load_file_index()

    def start_watching(self):
        """开始监听文件系统"""
        if self.is_running:
            logger.warning("file_system_already_watching")
            return

        try:
            # 创建基础目录
            self.base_path.mkdir(parents=True, exist_ok=True)

            # 创建子目录
            (self.base_path / "process_docs").mkdir(exist_ok=True)
            (self.base_path / "standards").mkdir(exist_ok=True)
            (self.base_path / "templates").mkdir(exist_ok=True)
            (self.base_path / "extracted").mkdir(exist_ok=True)

            # 设置文件系统监听器
            event_handler = FileSystemEventProcessor(
                self._process_file_event,
                self.watch_patterns
            )

            self.observer = Observer()
            self.observer.schedule(event_handler, str(self.base_path), recursive=True)
            self.observer.start()

            self.is_running = True
            logger.info("file_system_watching_started", base_path=str(self.base_path))

            # 处理现有文件
            asyncio.create_task(self._scan_existing_files())

        except Exception as e:
            logger.exception("file_system_watch_start_failed", error=str(e))
            self.stop_watching()

    def stop_watching(self):
        """停止监听文件系统"""
        if not self.is_running:
            return

        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None

            self.is_running = False
            logger.info("file_system_watching_stopped")

        except Exception as e:
            logger.exception("file_system_watch_stop_failed", error=str(e))

    async def _process_file_event(self, event_type: str, file_path: str):
        """处理文件系统事件"""
        with bind_context(file_path=file_path, event_type=event_type):
            logger.info("file_system_event_received", event_type=event_type, file_path=file_path)

            try:
                if event_type == "created":
                    await self._handle_file_created(file_path)
                elif event_type == "modified":
                    await self._handle_file_modified(file_path)
                elif event_type == "deleted":
                    await self._handle_file_deleted(file_path)

            except Exception as e:
                logger.exception("file_event_processing_failed",
                               event_type=event_type,
                               file_path=file_path,
                               error=str(e))

    async def _handle_file_created(self, file_path: str):
        """处理文件创建事件"""
        path = Path(file_path)

        # 检查是否是新文件（不是临时文件或隐藏文件）
        if path.name.startswith('.') or path.name.endswith('~'):
            return

        # 计算文件哈希
        file_hash = self._calculate_file_hash(path)

        # 检查是否已存在
        if file_path in self.file_index and self.file_index[file_path]["hash"] == file_hash:
            logger.debug("file_already_indexed", file_path=file_path)
            return

        # 创建文件记录
        file_info = await self._create_file_record(path, file_hash)

        # 添加到索引
        self.file_index[file_path] = file_info
        self._save_file_index()

        # 自动处理文件
        await self._auto_process_file(path, file_info)

    async def _handle_file_modified(self, file_path: str):
        """处理文件修改事件"""
        path = Path(file_path)

        # 重新计算哈希
        new_hash = self._calculate_file_hash(path)

        # 更新索引
        if file_path in self.file_index:
            old_info = self.file_index[file_path]
            if old_info["hash"] != new_hash:
                # 文件内容发生变化
                new_info = await self._create_file_record(path, new_hash)
                self.file_index[file_path] = new_info
                self._save_file_index()

                # 重新处理文件
                await self._auto_process_file(path, new_info)

    async def _handle_file_deleted(self, file_path: str):
        """处理文件删除事件"""
        if file_path in self.file_index:
            # 从索引中移除
            del self.file_index[file_path]
            self._save_file_index()

            logger.info("file_removed_from_index", file_path=file_path)

    async def _create_file_record(self, file_path: Path, file_hash: str) -> Dict[str, Any]:
        """创建文件记录"""
        stat = file_path.stat()

        # 基础文件信息
        record = {
            "path": str(file_path),
            "name": file_path.name,
            "extension": file_path.suffix,
            "size": stat.st_size,
            "hash": file_hash,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "indexed_at": datetime.now().isoformat(),
            "relative_path": str(file_path.relative_to(self.base_path)),
            "category": self._categorize_file(file_path)
        }

        # 根据文件类型添加额外信息
        if file_path.suffix.lower() == '.pdf':
            record.update(await self._extract_pdf_metadata(file_path))
        elif file_path.suffix.lower() in ['.docx', '.doc']:
            record.update(await self._extract_doc_metadata(file_path))
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            record.update(await self._extract_excel_metadata(file_path))

        return record

    def _categorize_file(self, file_path: Path) -> str:
        """分类文件"""
        # 根据路径分类
        if "process_docs" in file_path.parts:
            return "process_document"
        elif "standards" in file_path.parts:
            return "standard"
        elif "templates" in file_path.parts:
            return "template"
        elif "extracted" in file_path.parts:
            return "extracted_data"
        else:
            # 根据文件类型分类
            suffix = file_path.suffix.lower()
            if suffix == '.pdf':
                return "pdf_document"
            elif suffix in ['.docx', '.doc']:
                return "word_document"
            elif suffix in ['.xlsx', '.xls']:
                return "excel_document"
            elif suffix == '.md':
                return "markdown_document"
            else:
                return "other"

    async def _extract_pdf_metadata(self, file_path: Path) -> Dict[str, Any]:
        """提取PDF元数据"""
        try:
            import fitz

            doc = fitz.open(str(file_path))
            metadata = {
                "page_count": len(doc),
                "pdf_version": doc.pdf_catalog.get("Version", "Unknown"),
                "is_encrypted": doc.is_encrypted,
                "can_extract_text": not doc.is_repaired
            }

            # 提取文本预览（前500字符）
            text_preview = ""
            for page in doc[:min(3, len(doc))]:  # 只读取前3页
                text_preview += page.get_text()[:200]
                if len(text_preview) >= 500:
                    break

            metadata["text_preview"] = text_preview[:500]
            doc.close()

            # 如果是工艺文件，尝试提取表格
            if self._is_likely_process_document(file_path):
                with timer(logger, "pdf_table_preview_extraction", file_path=str(file_path)):
                    try:
                        from app.agents.tools.pdf_table_extractor import extract_mechanical_process_pdf
                        extraction_result = extract_mechanical_process_pdf(str(file_path))

                        metadata["has_tables"] = len(extraction_result.get("tables", [])) > 0
                        metadata["table_count"] = len(extraction_result.get("tables", []))
                        metadata["process_card_count"] = sum(
                            1 for t in extraction_result.get("tables", [])
                            if t.get("table_type") == "process_card"
                        )
                        metadata["extraction_status"] = "completed"
                    except Exception as e:
                        metadata["extraction_status"] = "failed"
                        metadata["extraction_error"] = str(e)

            return metadata

        except Exception as e:
            logger.warning("pdf_metadata_extraction_failed", file_path=str(file_path), error=str(e))
            return {"extraction_status": "failed", "error": str(e)}

    def _is_likely_process_document(self, file_path: Path) -> bool:
        """判断是否为工艺文件"""
        # 根据文件名判断
        filename = file_path.name.lower()
        keywords = ["工艺", "工序", "加工", "制造", "technical", "process"]

        return any(keyword in filename for keyword in keywords)

    async def _extract_doc_metadata(self, file_path: Path) -> Dict[str, Any]:
        """提取Word文档元数据"""
        # TODO: 实现Word文档元数据提取
        return {"type": "word_document", "extraction_status": "pending"}

    async def _extract_excel_metadata(self, file_path: Path) -> Dict[str, Any]:
        """提取Excel元数据"""
        # TODO: 实现Excel元数据提取
        return {"type": "excel_document", "extraction_status": "pending"}

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希值"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                return file_hash.hexdigest()
        except Exception as e:
            logger.error("file_hash_calculation_failed", file_path=str(file_path), error=str(e))
            return ""

    async def _auto_process_file(self, file_path: Path, file_info: Dict[str, Any]):
        """自动处理文件"""
        with bind_context(file_path=str(file_path), file_type=file_info.get("extension")):
            logger.info("auto_processing_file", file_path=str(file_path), category=file_info.get("category"))

            try:
                if file_info.get("category") == "process_document" and file_path.suffix.lower() == '.pdf':
                    await self._process_mechanical_pdf(file_path, file_info)
                elif file_info.get("category") == "pdf_document":
                    await self._process_general_pdf(file_path, file_info)
                elif file_info.get("category") in ["word_document", "excel_document"]:
                    await self._process_office_document(file_path, file_info)

            except Exception as e:
                logger.exception("auto_processing_failed", file_path=str(file_path), error=str(e))

    async def _process_mechanical_pdf(self, file_path: Path, file_info: Dict[str, Any]):
        """处理机械加工工艺PDF"""
        logger.info("processing_mechanical_pdf", file_path=str(file_path))

        try:
            from app.agents.tools.pdf_table_extractor import extract_mechanical_process_pdf

            # 提取PDF内容
            extraction_result = extract_mechanical_process_pdf(str(file_path))

            # 保存提取结果
            output_path = self.base_path / "extracted" / f"{file_path.stem}_extracted.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(extraction_result, f, ensure_ascii=False, indent=2)

            # 更新文件记录
            file_info["extraction_path"] = str(output_path)
            file_info["extraction_status"] = "completed"
            file_info["extraction_timestamp"] = datetime.now().isoformat()
            file_info["extracted_data"] = extraction_result

            logger.info("mechanical_pdf_processed",
                       file_path=str(file_path),
                       table_count=len(extraction_result.get("tables", [])),
                       output_path=str(output_path))

        except Exception as e:
            logger.exception("mechanical_pdf_processing_failed", file_path=str(file_path), error=str(e))
            file_info["extraction_status"] = "failed"
            file_info["extraction_error"] = str(e)

    async def _process_general_pdf(self, file_path: Path, file_info: Dict[str, Any]):
        """处理普通PDF文件"""
        logger.info("processing_general_pdf", file_path=str(file_path))

        # TODO: 实现普通PDF的处理逻辑
        file_info["processing_status"] = "pending"

    async def _process_office_document(self, file_path: Path, file_info: Dict[str, Any]):
        """处理Office文档"""
        logger.info("processing_office_document", file_path=str(file_path))

        # TODO: 实现Office文档的处理逻辑
        file_info["processing_status"] = "pending"

    async def _scan_existing_files(self):
        """扫描并处理现有文件"""
        logger.info("scanning_existing_files", base_path=str(self.base_path))

        try:
            for pattern in self.watch_patterns:
                for file_path in self.base_path.rglob(pattern):
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        # 检查是否已索引
                        str_path = str(file_path)
                        if str_path not in self.file_index:
                            # 创建文件记录
                            file_hash = self._calculate_file_hash(file_path)
                            file_info = await self._create_file_record(file_path, file_hash)

                            # 添加到索引
                            self.file_index[str_path] = file_info

                            # 自动处理
                            await self._auto_process_file(file_path, file_info)

            self._save_file_index()
            logger.info("existing_files_scan_completed", file_count=len(self.file_index))

        except Exception as e:
            logger.exception("existing_files_scan_failed", error=str(e))

    def _load_file_index(self):
        """加载文件索引"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.file_index = json.load(f)
                logger.info("file_index_loaded", count=len(self.file_index))
            else:
                self.file_index = {}
                logger.info("file_index_not_found", path=str(self.index_file))
        except Exception as e:
            logger.error("file_index_load_failed", error=str(e))
            self.file_index = {}

    def _save_file_index(self):
        """保存文件索引"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_index, f, ensure_ascii=False, indent=2)
            logger.debug("file_index_saved", count=len(self.file_index))
        except Exception as e:
            logger.error("file_index_save_failed", error=str(e))

    def get_file_context(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取文件的上下文信息"""
        return self.file_index.get(file_path)

    def get_all_files(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有文件（可选按分类过滤）"""
        files = list(self.file_index.values())

        if category:
            files = [f for f in files if f.get("category") == category]

        return files

    def get_recent_files(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近修改的文件"""
        from datetime import datetime, timedelta

        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_files = []
        for file_info in self.file_index.values():
            modified_time = datetime.fromisoformat(file_info.get("modified_at", ""))
            if modified_time > cutoff_time:
                recent_files.append(file_info)

        return recent_files

    def get_file_statistics(self) -> Dict[str, Any]:
        """获取文件统计信息"""
        stats = {
            "total_files": len(self.file_index),
            "by_category": {},
            "by_extension": {},
            "extraction_status": {
                "completed": 0,
                "pending": 0,
                "failed": 0
            }
        }

        for file_info in self.file_index.values():
            # 按分类统计
            category = file_info.get("category", "unknown")
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

            # 按扩展名统计
            ext = file_info.get("extension", "unknown")
            stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1

            # 提取状态统计
            status = file_info.get("extraction_status", "pending")
            if status in stats["extraction_status"]:
                stats["extraction_status"][status] += 1

        return stats


# 全局文件系统服务实例
file_system_service = FileSystemService()