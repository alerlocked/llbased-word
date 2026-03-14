"""
测试文件系统服务
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import asyncio

from app.services.file_system_service import FileSystemService


class TestFileSystemService:
    """文件系统服务测试类"""

    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作空间"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # 清理
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def file_service(self, temp_workspace):
        """创建文件系统服务实例"""
        service = FileSystemService(str(temp_workspace))
        yield service
        # 停止监听
        service.stop_watching()

    @pytest.mark.integration
    def test_service_initialization(self, temp_workspace):
        """测试服务初始化"""
        service = FileSystemService(str(temp_workspace))

        assert service.base_path == temp_workspace
        assert service.is_running == False
        assert len(service.watch_patterns) > 0

    @pytest.mark.integration
    def test_file_categorization(self, temp_workspace, file_service):
        """测试文件分类"""
        # 创建测试文件
        (temp_workspace / "process_docs").mkdir(exist_ok=True)
        (temp_workspace / "standards").mkdir(exist_ok=True)

        test_files = [
            temp_workspace / "process_docs" / "工艺卡.pdf",
            temp_workspace / "standards" / "标准.docx",
            temp_workspace / "template.md",
            temp_workspace / "random.txt"
        ]

        for file_path in test_files:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("test content")

        # 测试分类
        categories = {}
        for file_path in test_files:
            category = file_service._categorize_file(file_path)
            categories[str(file_path.relative_to(temp_workspace))] = category

        # 验证分类结果
        assert categories["process_docs/工艺卡.pdf"] == "process_document"
        assert categories["standards/标准.docx"] == "standard"
        assert categories["template.md"] == "markdown_document"
        assert categories["random.txt"] == "other"

    @pytest.mark.integration
    def test_file_hash_calculation(self, temp_workspace, file_service):
        """测试文件哈希计算"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello, World!")

        hash1 = file_service._calculate_file_hash(test_file)
        assert hash1 is not None
        assert len(hash1) == 32  # MD5哈希长度

        # 相同内容应该产生相同哈希
        hash2 = file_service._calculate_file_hash(test_file)
        assert hash1 == hash2

        # 不同内容应该产生不同哈希
        test_file.write_text("Different content")
        hash3 = file_service._calculate_file_hash(test_file)
        assert hash1 != hash3

    @pytest.mark.integration
    async def test_pdf_metadata_extraction(self, temp_workspace, file_service):
        """测试PDF元数据提取"""
        # 创建简单的测试PDF（如果可能）
        test_pdf = temp_workspace / "test.pdf"

        try:
            # 尝试创建一个简单的PDF
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "Test PDF Content")
            doc.save(str(test_pdf))
            doc.close()

            # 测试元数据提取
            metadata = await file_service._extract_pdf_metadata(test_pdf)

            assert isinstance(metadata, dict)
            assert "page_count" in metadata
            assert metadata["page_count"] == 1
            assert "text_preview" in metadata

        except ImportError:
            pytest.skip("PyMuPDF not available")

    @pytest.mark.integration
    def test_is_likely_process_document(self, temp_workspace, file_service):
        """测试工艺文件识别"""
        test_cases = [
            ("工艺卡.pdf", True),
            ("工序说明书.docx", True),
            ("加工工艺.xlsx", True),
            ("制造流程.txt", True),
            ("technical_process.pdf", True),
            ("random_file.pdf", False),
            ("notes.txt", False)
        ]

        for filename, expected in test_cases:
            file_path = temp_workspace / filename
            result = file_service._is_likely_process_document(file_path)
            assert result == expected, f"Failed for {filename}"

    @pytest.mark.integration
    def test_file_index_operations(self, temp_workspace, file_service):
        """测试文件索引操作"""
        # 创建测试文件
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Test content")

        # 创建文件记录
        file_hash = file_service._calculate_file_hash(test_file)
        file_info = file_service._create_file_record(test_file, file_hash)

        # 添加到索引
        file_service.file_index[str(test_file)] = file_info
        file_service._save_file_index()

        # 验证索引
        assert str(test_file) in file_service.file_index
        retrieved_info = file_service.get_file_context(str(test_file))
        assert retrieved_info is not None
        assert retrieved_info["hash"] == file_hash

        # 删除文件
        del file_service.file_index[str(test_file)]
        file_service._save_file_index()

        assert str(test_file) not in file_service.file_index

    @pytest.mark.integration
    def test_file_statistics(self, temp_workspace, file_service):
        """测试文件统计"""
        # 创建不同类型的文件
        categories = {
            "process_document": ["process1.pdf", "process2.pdf"],
            "standard": ["std1.docx"],
            "template": ["template.md"]
        }

        for category, files in categories.items():
            for filename in files:
                file_path = temp_workspace / filename
                file_path.write_text("test content")

                # 手动添加到索引（模拟已索引的文件）
                file_hash = file_service._calculate_file_hash(file_path)
                file_info = {
                    "path": str(file_path),
                    "name": filename,
                    "extension": file_path.suffix,
                    "category": category,
                    "hash": file_hash,
                    "created_at": "2024-01-01T00:00:00",
                    "modified_at": "2024-01-01T00:00:00",
                    "indexed_at": "2024-01-01T00:00:00"
                }
                file_service.file_index[str(file_path)] = file_info

        # 获取统计信息
        stats = file_service.get_file_statistics()

        assert stats["total_files"] == 4
        assert stats["by_category"]["process_document"] == 2
        assert stats["by_category"]["standard"] == 1
        assert stats["by_category"]["template"] == 1
        assert stats["by_extension"][".pdf"] == 2
        assert stats["by_extension"][".docx"] == 1
        assert stats["by_extension"][".md"] == 1

    @pytest.mark.integration
    async def test_scan_existing_files(self, temp_workspace, file_service):
        """测试扫描现有文件"""
        # 创建一些测试文件
        test_files = [
            temp_workspace / "existing1.pdf",
            temp_workspace / "existing2.docx",
            temp_workspace / "subdir" / "existing3.txt"
        ]

        for file_path in test_files:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("existing content")

        # 扫描现有文件
        await file_service._scan_existing_files()

        # 验证所有文件都被索引
        assert len(file_service.file_index) == 3

        for file_path in test_files:
            assert str(file_path) in file_service.file_index

    @pytest.mark.integration
    def test_recent_files_query(self, temp_workspace, file_service):
        """测试最近文件查询"""
        from datetime import datetime, timedelta

        # 创建带有不同时间戳的文件记录
        now = datetime.now()
        old_time = (now - timedelta(hours=48)).isoformat()
        recent_time = (now - timedelta(hours=12)).isoformat()

        # 添加测试数据到索引
        file_service.file_index = {
            "old_file.pdf": {
                "path": str(temp_workspace / "old_file.pdf"),
                "modified_at": old_time,
                "category": "process_document"
            },
            "recent_file.docx": {
                "path": str(temp_workspace / "recent_file.docx"),
                "modified_at": recent_time,
                "category": "process_document"
            }
        }

        # 查询最近24小时的文件
        recent_files = file_service.get_recent_files(hours=24)
        recent_process_docs = [f for f in recent_files if f.get("category") == "process_document"]

        assert len(recent_process_docs) == 1
        assert "recent_file.docx" in recent_process_docs[0]["path"]

    @pytest.mark.integration
    async def test_file_processing_workflow(self, temp_workspace, file_service):
        """测试文件处理工作流"""
        # 创建工艺文档目录
        process_dir = temp_workspace / "process_docs"
        process_dir.mkdir(exist_ok=True)

        # 创建一个模拟的工艺PDF文件
        test_pdf = process_dir / "工艺卡.pdf"
        test_pdf.write_text("模拟PDF内容")

        # 模拟文件创建事件
        await file_service._handle_file_created(str(test_pdf))

        # 验证文件被正确处理
        file_info = file_service.get_file_context(str(test_pdf))
        assert file_info is not None
        assert file_info["category"] == "process_document"
        assert file_info["extension"] == ".pdf"

    def test_error_handling(self, temp_workspace, file_service):
        """测试错误处理"""
        # 测试不存在的路径
        result = file_service.get_file_context("non_existent.pdf")
        assert result is None

        # 测试无效路径
        stats = file_service.get_file_statistics()
        assert isinstance(stats, dict)
        assert "total_files" in stats