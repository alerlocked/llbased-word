"""
Tests for PDF Services

Validates:
1. PDFQueueManager functionality
2. PDFWatcherService functionality
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from datetime import datetime

from app.services.pdf_queue_manager import (
    PDFQueueManager,
    PDFTask,
    PDFTaskStatus,
    PDFTaskPriority,
    PDFQueueStats,
    get_pdf_queue_manager,
)
from app.services.pdf_watcher_service import (
    PDFWatcherService,
    PDFFileEventHandler,
    get_pdf_watcher_service,
)


class TestPDFTask:
    """Tests for PDFTask dataclass"""

    def test_pdf_task_creation(self):
        """Test creating a PDFTask"""
        task = PDFTask(
            task_id="test_001",
            source_path="/source/test.pdf",
            output_path="/output/test.html",
            file_hash="abc123",
            file_size=1024
        )

        assert task.task_id == "test_001"
        assert task.status == PDFTaskStatus.PENDING
        assert task.priority == PDFTaskPriority.NORMAL
        assert task.progress == 0

    def test_pdf_task_to_dict(self):
        """Test PDFTask to_dict method"""
        task = PDFTask(
            task_id="test_002",
            source_path="/source/test.pdf",
            output_path="/output/test.html",
            file_hash="def456",
            file_size=2048,
            status=PDFTaskStatus.COMPLETED,
            progress=100
        )

        task_dict = task.to_dict()

        assert task_dict["task_id"] == "test_002"
        assert task_dict["status"] == "completed"
        assert task_dict["progress"] == 100
        assert "created_at" in task_dict


class TestPDFQueueStats:
    """Tests for PDFQueueStats dataclass"""

    def test_queue_stats_defaults(self):
        """Test PDFQueueStats default values"""
        stats = PDFQueueStats()

        assert stats.total_tasks == 0
        assert stats.pending_tasks == 0
        assert stats.max_workers == 2

    def test_queue_stats_to_dict(self):
        """Test PDFQueueStats to_dict method"""
        stats = PDFQueueStats(
            total_tasks=10,
            pending_tasks=5,
            processing_tasks=2,
            completed_tasks=3,
            max_workers=4
        )

        stats_dict = stats.to_dict()

        assert stats_dict["total_tasks"] == 10
        assert stats_dict["max_workers"] == 4


class TestPDFQueueManager:
    """Tests for PDFQueueManager"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def queue_manager(self, temp_dir):
        """Create a PDFQueueManager instance"""
        manager = PDFQueueManager(
            max_concurrent=2,
            output_base_path=os.path.join(temp_dir, "output"),
            state_file=os.path.join(temp_dir, "state.json")
        )
        yield manager
        # Cleanup
        asyncio.get_event_loop().run_until_complete(manager.stop())

    @pytest.fixture
    def sample_pdf(self, temp_dir):
        """Create a sample PDF file for testing"""
        pdf_path = os.path.join(temp_dir, "test.pdf")
        # Create a minimal PDF-like file
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\ntest content\n%%EOF')
        return pdf_path

    def test_queue_manager_initialization(self, temp_dir):
        """Test PDFQueueManager initialization"""
        manager = PDFQueueManager(
            max_concurrent=3,
            output_base_path=os.path.join(temp_dir, "output"),
            state_file=os.path.join(temp_dir, "state.json")
        )

        assert manager.max_concurrent == 3
        assert manager.output_base_path.name == "output"

    @pytest.mark.asyncio
    async def test_add_task(self, queue_manager, sample_pdf):
        """Test adding a task to the queue"""
        task_id = await queue_manager.add_task(sample_pdf)

        assert task_id is not None
        assert task_id.startswith("pdf_")

        task = queue_manager.get_task(task_id)
        assert task is not None
        assert task.status == PDFTaskStatus.QUEUED

    @pytest.mark.asyncio
    async def test_add_task_nonexistent_file(self, queue_manager):
        """Test adding a task with non-existent file"""
        task_id = await queue_manager.add_task("/nonexistent/file.pdf")

        assert task_id is None

    @pytest.mark.asyncio
    async def test_add_task_duplicate(self, queue_manager, sample_pdf):
        """Test adding duplicate task"""
        task_id1 = await queue_manager.add_task(sample_pdf)
        task_id2 = await queue_manager.add_task(sample_pdf)

        # Should return same task ID for duplicate
        assert task_id1 == task_id2

    @pytest.mark.asyncio
    async def test_get_stats(self, queue_manager, sample_pdf):
        """Test getting queue statistics"""
        await queue_manager.add_task(sample_pdf)

        stats = queue_manager.get_stats()

        assert stats.total_tasks >= 1
        assert stats.max_workers == 2

    @pytest.mark.asyncio
    async def test_cancel_task(self, queue_manager, sample_pdf):
        """Test cancelling a task"""
        task_id = await queue_manager.add_task(sample_pdf)

        success = await queue_manager.cancel_task(task_id)

        assert success is True
        task = queue_manager.get_task(task_id)
        assert task.status == PDFTaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, queue_manager):
        """Test cancelling a non-existent task"""
        success = await queue_manager.cancel_task("nonexistent_task")
        assert success is False

    @pytest.mark.asyncio
    async def test_get_all_tasks(self, queue_manager, sample_pdf):
        """Test getting all tasks"""
        await queue_manager.add_task(sample_pdf)

        tasks = queue_manager.get_all_tasks()

        assert len(tasks) >= 1

    @pytest.mark.asyncio
    async def test_get_tasks_by_status(self, queue_manager, sample_pdf):
        """Test getting tasks filtered by status"""
        await queue_manager.add_task(sample_pdf)

        tasks = queue_manager.get_all_tasks(status=PDFTaskStatus.QUEUED)

        for task in tasks:
            assert task.status == PDFTaskStatus.QUEUED

    @pytest.mark.asyncio
    async def test_get_task_by_path(self, queue_manager, sample_pdf):
        """Test getting task by source path"""
        await queue_manager.add_task(sample_pdf)

        task = queue_manager.get_task_by_path(sample_pdf)

        assert task is not None
        assert task.source_path == sample_pdf

    @pytest.mark.asyncio
    async def test_batch_add_tasks(self, queue_manager, temp_dir):
        """Test batch adding tasks"""
        # Create multiple PDF files
        pdf_files = []
        for i in range(3):
            pdf_path = os.path.join(temp_dir, f"test{i}.pdf")
            with open(pdf_path, 'wb') as f:
                f.write(b'%PDF-1.4\ntest\n%%EOF')
            pdf_files.append(pdf_path)

        task_ids = await queue_manager.add_tasks_batch(pdf_files)

        assert len(task_ids) == 3

    @pytest.mark.asyncio
    async def test_start_and_stop(self, queue_manager):
        """Test starting and stopping the queue manager"""
        await queue_manager.start()
        assert queue_manager._running is True

        await queue_manager.stop()
        assert queue_manager._running is False

    def test_generate_task_id(self, queue_manager, sample_pdf):
        """Test task ID generation"""
        task_id = queue_manager._generate_task_id(Path(sample_pdf))

        assert task_id.startswith("pdf_")
        assert len(task_id) == 16  # "pdf_" + 12 hex chars

    def test_get_output_path(self, queue_manager, sample_pdf):
        """Test output path generation"""
        output_path = queue_manager._get_output_path(Path(sample_pdf))

        assert output_path.suffix == ".html"
        assert output_path.name == "test.html"


class TestPDFFileEventHandler:
    """Tests for PDFFileEventHandler"""

    def test_event_handler_initialization(self):
        """Test event handler initialization"""
        handler = PDFFileEventHandler(callback=lambda e, p: None)

        assert handler.watched_extensions == ['.pdf']
        assert '.tmp' in handler.ignore_patterns

    def test_should_process_pdf(self):
        """Test _should_process with PDF file"""
        handler = PDFFileEventHandler(callback=lambda e, p: None)

        assert handler._should_process("/path/to/file.pdf") is True

    def test_should_process_non_pdf(self):
        """Test _should_process with non-PDF file"""
        handler = PDFFileEventHandler(callback=lambda e, p: None)

        assert handler._should_process("/path/to/file.txt") is False
        assert handler._should_process("/path/to/file.doc") is False

    def test_should_process_temp_file(self):
        """Test _should_process with temp file"""
        handler = PDFFileEventHandler(callback=lambda e, p: None)

        assert handler._should_process("/path/to/file.tmp") is False
        assert handler._should_process("/path/to/.hidden.pdf") is False


class TestPDFWatcherService:
    """Tests for PDFWatcherService"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def watcher_service(self, temp_dir):
        """Create a PDFWatcherService instance"""
        from app.services.pdf_queue_manager import PDFQueueManager

        queue_manager = PDFQueueManager(
            max_concurrent=2,
            output_base_path=os.path.join(temp_dir, "output"),
            state_file=os.path.join(temp_dir, "state.json")
        )

        service = PDFWatcherService(
            watch_paths=[temp_dir],
            queue_manager=queue_manager,
            auto_start=False
        )
        yield service

    def test_watcher_service_initialization(self, temp_dir):
        """Test watcher service initialization"""
        service = PDFWatcherService(
            watch_paths=[temp_dir],
            auto_start=False
        )

        assert len(service.watch_paths) == 1
        assert service._is_running is False

    def test_add_watch_path(self, watcher_service, temp_dir):
        """Test adding a watch path"""
        new_path = os.path.join(temp_dir, "subdir")
        os.makedirs(new_path)

        watcher_service.add_watch_path(new_path)

        assert Path(new_path) in watcher_service.watch_paths

    def test_remove_watch_path(self, watcher_service, temp_dir):
        """Test removing a watch path"""
        watcher_service.remove_watch_path(temp_dir)

        assert Path(temp_dir) not in watcher_service.watch_paths

    def test_get_status(self, watcher_service):
        """Test getting watcher status"""
        status = watcher_service.get_status()

        assert "is_running" in status
        assert "watch_paths" in status
        assert "queue_stats" in status

    @pytest.mark.asyncio
    async def test_start_and_stop(self, watcher_service):
        """Test starting and stopping the watcher"""
        await watcher_service.start()
        assert watcher_service._is_running is True

        await watcher_service.stop()
        assert watcher_service._is_running is False


class TestGlobalInstances:
    """Tests for global instance functions"""

    def test_get_pdf_queue_manager_singleton(self):
        """Test get_pdf_queue_manager returns singleton"""
        # Reset the global instance
        import app.services.pdf_queue_manager as module
        module._pdf_queue_manager = None

        manager1 = get_pdf_queue_manager()
        manager2 = get_pdf_queue_manager()

        assert manager1 is manager2

    def test_get_pdf_watcher_service_singleton(self):
        """Test get_pdf_watcher_service returns singleton"""
        # Reset the global instance
        import app.services.pdf_watcher_service as module
        module._pdf_watcher_service = None

        service1 = get_pdf_watcher_service()
        service2 = get_pdf_watcher_service()

        assert service1 is service2
