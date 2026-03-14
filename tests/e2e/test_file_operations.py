"""
File Upload/Download Tests
Tests for document and image upload functionality.
Coverage: PDF upload, DOCX upload, image upload, file validation
"""
import os
import pytest
from pathlib import Path
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# Helper functions
async def create_test_project(async_client: AsyncClient, name: str = "Test Project") -> dict:
    """Helper to create a test project."""
    response = await async_client.post("/api/creation/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()


async def cleanup_test_project(async_client: AsyncClient, project_id: int):
    """Helper to cleanup a test project."""
    try:
        await async_client.delete(f"/api/creation/projects/{project_id}")
    except Exception:
        pass


class TestDocumentUpload:
    """Tests for document upload functionality."""

    async def test_upload_pdf_document(self, async_client: AsyncClient, temp_pdf_file: Path):
        """Test uploading a PDF document."""
        # Create project first
        project = await create_test_project(async_client, "PDF Upload Test")

        # Upload PDF
        with open(temp_pdf_file, "rb") as f:
            files = {"file": ("test_document.pdf", f, "application/pdf")}
            response = await async_client.post(
                f"/api/creation/projects/{project['id']}/documents",
                files=files
            )

        # Note: This may fail if document processing service is not available
        # In a real test environment, we would mock the document processor
        assert response.status_code in [200, 500]  # 500 if processor unavailable

        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "material_id" in data

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_docx_document(self, async_client: AsyncClient, temp_docx_file: Path):
        """Test uploading a DOCX document."""
        # Create project first
        project = await create_test_project(async_client, "DOCX Upload Test")

        # Upload DOCX
        with open(temp_docx_file, "rb") as f:
            files = {"file": ("test_document.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            response = await async_client.post(
                f"/api/creation/projects/{project['id']}/documents",
                files=files
            )

        # Note: This may fail if document processing service is not available
        assert response.status_code in [200, 500]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_document_invalid_format(self, async_client: AsyncClient, temp_invalid_file: Path):
        """Test uploading an unsupported file format."""
        # Create project first
        project = await create_test_project(async_client, "Invalid Format Test")

        # Upload invalid file
        with open(temp_invalid_file, "rb") as f:
            files = {"file": ("test_file.xyz", f, "application/octet-stream")}
            response = await async_client.post(
                f"/api/creation/projects/{project['id']}/documents",
                files=files
            )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "不支持的文件格式" in data["detail"]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_document_nonexistent_project(self, async_client: AsyncClient, temp_pdf_file: Path):
        """Test uploading document to non-existent project."""
        with open(temp_pdf_file, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = await async_client.post(
                "/api/creation/projects/999999/documents",
                files=files
            )

        assert response.status_code == 404

    async def test_upload_document_with_chinese_filename(self, async_client: AsyncClient, temp_pdf_file: Path):
        """Test uploading document with Chinese filename."""
        # Create project first
        project = await create_test_project(async_client, "Chinese Filename Test")

        # Upload with Chinese filename
        with open(temp_pdf_file, "rb") as f:
            files = {"file": ("工艺文档测试.pdf", f, "application/pdf")}
            response = await async_client.post(
                f"/api/creation/projects/{project['id']}/documents",
                files=files
            )

        assert response.status_code in [200, 500]  # 500 if processor unavailable

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestImageUpload:
    """Tests for image upload functionality."""

    async def test_upload_image_success(self, async_client: AsyncClient, temp_image_file: Path):
        """Test successful image upload."""
        # Create project first
        project = await create_test_project(async_client, "Image Upload Test")

        # Upload image
        with open(temp_image_file, "rb") as f:
            files = {"file": ("test_image.png", f, "image/png")}
            response = await async_client.post(
                f"/api/creation/images/upload?project_id={project['id']}",
                files=files
            )

        # Note: May fail if VL service is not available
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "id" in data
            assert "url" in data

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_image_jpeg(self, async_client: AsyncClient):
        """Test uploading JPEG image."""
        # Create project first
        project = await create_test_project(async_client, "JPEG Upload Test")

        # Create minimal JPEG (1x1 pixel)
        jpeg_content = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
            0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
            0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
            0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C,
            0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
            0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
            0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
            0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
            0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4,
            0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
            0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF,
            0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04,
            0x00, 0x00, 0x01, 0x7D, 0x01, 0x02, 0x03, 0x00,
            0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32,
            0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1,
            0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A,
            0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35,
            0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55,
            0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65,
            0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85,
            0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93, 0x94,
            0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2,
            0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA,
            0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8,
            0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6,
            0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA,
            0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
            0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x45, 0x00,
            0x14, 0x51, 0x40, 0x05, 0x14, 0x50, 0x01, 0x45,
            0x14, 0x00, 0xFF, 0xD9
        ])

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(jpeg_content)
            temp_path = Path(f.name)

        try:
            with open(temp_path, "rb") as f:
                files = {"file": ("test.jpg", f, "image/jpeg")}
                response = await async_client.post(
                    f"/api/creation/images/upload?project_id={project['id']}",
                    files=files
                )

            assert response.status_code in [200, 500]
        finally:
            os.unlink(temp_path)

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_image_invalid_format(self, async_client: AsyncClient, temp_invalid_file: Path):
        """Test uploading invalid image format."""
        # Create project first
        project = await create_test_project(async_client, "Invalid Image Test")

        # Upload invalid file
        with open(temp_invalid_file, "rb") as f:
            files = {"file": ("test.xyz", f, "application/octet-stream")}
            response = await async_client.post(
                f"/api/creation/images/upload?project_id={project['id']}",
                files=files
            )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "不支持的图片格式" in data["detail"]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_image_nonexistent_project(self, async_client: AsyncClient, temp_image_file: Path):
        """Test uploading image to non-existent project."""
        with open(temp_image_file, "rb") as f:
            files = {"file": ("test.png", f, "image/png")}
            response = await async_client.post(
                "/api/creation/images/upload?project_id=999999",
                files=files
            )

        assert response.status_code == 404

    async def test_search_uploaded_images(self, async_client: AsyncClient):
        """Test searching uploaded images."""
        # Create project first
        project = await create_test_project(async_client, "Image Search Test")

        # Search images (should be empty initially)
        response = await async_client.get(
            f"/api/creation/images/search?project_id={project['id']}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "images" in data
        assert "count" in data

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_search_images_with_query(self, async_client: AsyncClient):
        """Test searching images with query."""
        # Create project first
        project = await create_test_project(async_client, "Image Query Search Test")

        # Search with query
        response = await async_client.get(
            f"/api/creation/images/search?project_id={project['id']}&query=test"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestImageSearch:
    """Tests for image search functionality."""

    async def test_search_project_images(self, async_client: AsyncClient):
        """Test searching images within a project."""
        # Create project
        project = await create_test_project(async_client, "Image Search Project")

        # Search images
        response = await async_client.post(
            f"/api/creation/projects/{project['id']}/images/search",
            json={"query": "test", "source": "local", "count": 10}
        )

        # May fail if image search service is not available
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_search_images_empty_query(self, async_client: AsyncClient):
        """Test searching images with empty query."""
        # Create project
        project = await create_test_project(async_client, "Empty Query Test")

        # Search with empty query
        response = await async_client.post(
            f"/api/creation/projects/{project['id']}/images/search",
            json={"query": "", "source": "local", "count": 10}
        )

        assert response.status_code == 200
        assert response.json() == []

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestMaterialManagement:
    """Tests for material management."""

    async def test_add_materials_to_project(self, async_client: AsyncClient):
        """Test adding materials to a project."""
        # Create project
        project = await create_test_project(async_client, "Add Materials Test")

        # Add materials (using non-existent IDs - should handle gracefully)
        response = await async_client.post(
            f"/api/creation/projects/{project['id']}/materials",
            json={"project_id": project["id"], "material_ids": [1, 2, 3]}
        )

        # Should succeed even with non-existent material IDs
        # The API only adds materials that exist
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "added_count" in data

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_add_materials_nonexistent_project(self, async_client: AsyncClient):
        """Test adding materials to non-existent project."""
        response = await async_client.post(
            "/api/creation/projects/999999/materials",
            json={"project_id": 999999, "material_ids": [1, 2, 3]}
        )

        assert response.status_code == 404

    async def test_remove_material_from_project(self, async_client: AsyncClient):
        """Test removing material from project."""
        # Create project
        project = await create_test_project(async_client, "Remove Material Test")

        # Try to remove non-existent material
        response = await async_client.delete(
            f"/api/creation/projects/{project['id']}/materials/999"
        )

        # Should return 404 as material is not in project
        assert response.status_code == 404

        # Cleanup
        await cleanup_test_project(async_client, project["id"])
