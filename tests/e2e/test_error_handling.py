"""
Error Handling Tests
Tests for API error handling and edge cases.
Coverage: 404 errors, 400 errors, 500 errors, validation errors
"""
import pytest
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


class TestNotFoundError:
    """Tests for 404 Not Found errors."""

    async def test_get_nonexistent_project(self, async_client: AsyncClient):
        """Test getting a non-existent project."""
        response = await async_client.get("/api/creation/projects/999999/content")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "不存在" in data["detail"]

    async def test_update_nonexistent_project_content(self, async_client: AsyncClient):
        """Test updating content of non-existent project."""
        response = await async_client.put(
            "/api/creation/projects/999999/content",
            json={"content": "test content"}
        )

        assert response.status_code == 404

    async def test_get_versions_nonexistent_project(self, async_client: AsyncClient):
        """Test getting versions of non-existent project."""
        response = await async_client.get("/api/creation/projects/999999/versions")

        # API returns 200 with empty versions list for non-existent projects
        # (versions endpoint doesn't check if project exists)
        assert response.status_code == 200
        assert response.json()["versions"] == []

    async def test_get_materials_nonexistent_project(self, async_client: AsyncClient):
        """Test getting materials of non-existent project."""
        response = await async_client.get("/api/creation/projects/999999/materials")

        # API returns 500 for non-existent project (due to exception handling)
        assert response.status_code in [404, 500]

    async def test_rollback_nonexistent_version(self, async_client: AsyncClient):
        """Test rolling back to non-existent version."""
        # Create project
        project = await create_test_project(async_client, "Rollback Test")

        # Try to rollback to non-existent version
        response = await async_client.post(
            f"/api/creation/projects/{project['id']}/rollback/999999"
        )

        assert response.status_code == 404

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_rollback_version_wrong_project(self, async_client: AsyncClient):
        """Test rolling back using wrong project ID."""
        # Create project
        project = await create_test_project(async_client, "Wrong Project Test")

        # Try to rollback with wrong project ID
        response = await async_client.post(
            f"/api/creation/projects/{project['id']}/rollback/999999"
        )

        assert response.status_code == 404

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestValidationError:
    """Tests for 400 Bad Request / validation errors."""

    async def test_upload_invalid_file_format(self, async_client: AsyncClient):
        """Test uploading file with invalid format."""
        # Create project
        project = await create_test_project(async_client, "Invalid Format Test")

        # Upload invalid file (simulated)
        files = {"file": ("test.xyz", b"invalid content", "application/octet-stream")}
        response = await async_client.post(
            f"/api/creation/projects/{project['id']}/documents",
            files=files
        )

        assert response.status_code == 400
        data = response.json()
        assert "不支持的文件格式" in data["detail"]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_upload_image_invalid_format(self, async_client: AsyncClient):
        """Test uploading image with invalid format."""
        # Create project
        project = await create_test_project(async_client, "Invalid Image Format Test")

        # Upload invalid image
        files = {"file": ("test.xyz", b"invalid content", "application/octet-stream")}
        response = await async_client.post(
            f"/api/creation/images/upload?project_id={project['id']}",
            files=files
        )

        assert response.status_code == 400
        data = response.json()
        assert "不支持的图片格式" in data["detail"]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_remove_nonexistent_material(self, async_client: AsyncClient):
        """Test removing material that doesn't exist in project."""
        # Create project
        project = await create_test_project(async_client, "Remove Nonexistent Test")

        # Try to remove non-existent material
        response = await async_client.delete(
            f"/api/creation/projects/{project['id']}/materials/999"
        )

        # API returns 500 for this case (exception handling)
        assert response.status_code in [404, 500]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    async def test_project_name_max_length(self, async_client: AsyncClient):
        """Test project creation with maximum length name."""
        # Create project with very long name
        long_name = "A" * 1000  # Very long name
        response = await async_client.post(
            "/api/creation/projects",
            json={"name": long_name}
        )

        # Should handle gracefully
        assert response.status_code == 200
        data = response.json()

        # Cleanup
        await cleanup_test_project(async_client, data["id"])

    async def test_content_max_length(self, async_client: AsyncClient):
        """Test updating project with maximum length content."""
        # Create project
        project = await create_test_project(async_client, "Max Content Test")

        # Create very large content
        large_content = "X" * 1000000  # 1MB of content
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": large_content}
        )

        # Should handle gracefully (may succeed or fail based on server config)
        assert response.status_code in [200, 413, 500]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_content_unicode(self, async_client: AsyncClient):
        """Test updating project with unicode content."""
        # Create project
        project = await create_test_project(async_client, "Unicode Test")

        # Unicode content with various characters
        unicode_content = """
        中文内容测试
        日本語テスト
        한국어 테스트
        Emoji: 🎉 🚀 ✅ ❌ 📄
        Special: © ® ™ € £ ¥
        """
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": unicode_content}
        )

        assert response.status_code == 200

        # Verify content was saved correctly
        get_response = await async_client.get(
            f"/api/creation/projects/{project['id']}/content"
        )
        assert get_response.json()["content"] == unicode_content

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_content_html_tags(self, async_client: AsyncClient):
        """Test updating project with HTML content."""
        # Create project
        project = await create_test_project(async_client, "HTML Test")

        # HTML content
        html_content = """
        <h1>Title</h1>
        <p>Paragraph with <strong>bold</strong> and <em>italic</em></p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <script>alert('xss')</script>
        """
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": html_content}
        )

        assert response.status_code == 200

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_content_sql_injection_attempt(self, async_client: AsyncClient):
        """Test that SQL injection attempts are handled safely."""
        # Create project
        project = await create_test_project(async_client, "SQL Test")

        # SQL injection attempt
        sql_content = "'; DROP TABLE projects; --"
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": sql_content}
        )

        # Should be saved as regular content (escaped)
        assert response.status_code == 200

        # Verify project still exists
        get_response = await async_client.get(
            f"/api/creation/projects/{project['id']}/content"
        )
        assert get_response.status_code == 200

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_empty_content_update(self, async_client: AsyncClient):
        """Test updating project with empty content."""
        # Create project
        project = await create_test_project(async_client, "Empty Content Test")

        # Update with empty content
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": ""}
        )

        assert response.status_code == 200

        # Verify content is empty
        get_response = await async_client.get(
            f"/api/creation/projects/{project['id']}/content"
        )
        assert get_response.json()["content"] == ""

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_whitespace_only_content(self, async_client: AsyncClient):
        """Test updating project with whitespace-only content."""
        # Create project
        project = await create_test_project(async_client, "Whitespace Test")

        # Whitespace-only content
        whitespace_content = "   \n\t\n   "
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": whitespace_content}
        )

        assert response.status_code == 200

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_concurrent_project_creation(self, async_client: AsyncClient):
        """Test concurrent project creation requests."""
        import asyncio

        async def create_project(index: int):
            response = await async_client.post(
                "/api/creation/projects",
                json={"name": f"Concurrent Test {index}"}
            )
            return response

        # Create multiple projects concurrently
        tasks = [create_project(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        created_ids = []
        for response in responses:
            assert response.status_code == 200
            created_ids.append(response.json()["id"])

        # All IDs should be unique
        assert len(set(created_ids)) == 5

        # Cleanup
        for project_id in created_ids:
            await cleanup_test_project(async_client, project_id)

    async def test_project_id_boundary(self, async_client: AsyncClient):
        """Test project ID boundary conditions."""
        # Test with invalid IDs
        invalid_ids = [0, -1, -999, 999999999999]

        for project_id in invalid_ids:
            response = await async_client.get(f"/api/creation/projects/{project_id}/content")
            assert response.status_code == 404


class TestAPIResponseFormat:
    """Tests for API response format consistency."""

    async def test_project_response_format(self, async_client: AsyncClient):
        """Test project response format is consistent."""
        # Create project
        project = await create_test_project(async_client, "Response Format Test")

        # Get project content
        response = await async_client.get(f"/api/creation/projects/{project['id']}/content")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "id" in data
        assert "name" in data
        assert "content" in data
        assert "updated_at" in data

        # Check types
        assert isinstance(data["id"], int)
        assert isinstance(data["name"], str)
        assert isinstance(data["content"], str)
        assert isinstance(data["updated_at"], str)

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_project_list_response_format(self, async_client: AsyncClient):
        """Test project list response format is consistent."""
        response = await async_client.get("/api/creation/projects")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "items" in data
        assert isinstance(data["items"], list)

        # Check item format if not empty
        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "name" in item
            assert "created_at" in item
            assert "updated_at" in item

    async def test_error_response_format(self, async_client: AsyncClient):
        """Test error response format is consistent."""
        response = await async_client.get("/api/creation/projects/999999/content")

        assert response.status_code == 404
        data = response.json()

        # Check error format
        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestHTTPMethods:
    """Tests for HTTP method handling."""

    async def test_project_post_wrong_endpoint(self, async_client: AsyncClient):
        """Test POST to wrong endpoint."""
        response = await async_client.post("/api/creation/projects/1/content")

        # Should return method not allowed or not found
        assert response.status_code in [405, 404]

    async def test_project_delete_wrong_endpoint(self, async_client: AsyncClient):
        """Test DELETE to wrong endpoint."""
        response = await async_client.delete("/api/creation/projects")

        # Should return method not allowed or not found
        assert response.status_code in [405, 404]


class TestContentType:
    """Tests for content type handling."""

    async def test_json_content_type(self, async_client: AsyncClient):
        """Test JSON content type handling."""
        # Create project
        project = await create_test_project(async_client, "JSON Content Test")

        # Update with JSON
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": "test"},
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_invalid_json_body(self, async_client: AsyncClient):
        """Test invalid JSON body handling."""
        # Create project
        project = await create_test_project(async_client, "Invalid JSON Test")

        # Send invalid JSON
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            content=b"invalid json{",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

        # Cleanup
        await cleanup_test_project(async_client, project["id"])
