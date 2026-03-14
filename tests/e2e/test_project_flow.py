"""
Project Creation Flow Tests
Tests for project CRUD operations and content management.
Coverage: Project creation, listing, content update, deletion
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


class TestProjectCreation:
    """Tests for project creation flow."""

    async def test_create_project_success(self, async_client: AsyncClient, sample_project_data: dict):
        """Test successful project creation."""
        # Create project
        response = await async_client.post("/api/creation/projects", json=sample_project_data)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == sample_project_data["name"]
        assert "created_at" in data
        assert "updated_at" in data

        # Cleanup
        await cleanup_test_project(async_client, data["id"])

    async def test_create_project_default_name(self, async_client: AsyncClient):
        """Test project creation with default name."""
        response = await async_client.post("/api/creation/projects", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新项目"  # Default name from API

        # Cleanup
        await cleanup_test_project(async_client, data["id"])

    async def test_create_project_with_chinese_name(self, async_client: AsyncClient):
        """Test project creation with Chinese characters."""
        chinese_name = "工艺文件测试项目"
        response = await async_client.post("/api/creation/projects", json={"name": chinese_name})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == chinese_name

        # Cleanup
        await cleanup_test_project(async_client, data["id"])

    async def test_create_project_with_special_characters(self, async_client: AsyncClient):
        """Test project creation with special characters."""
        special_name = "Project-Test_2024 (v1.0)"
        response = await async_client.post("/api/creation/projects", json={"name": special_name})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == special_name

        # Cleanup
        await cleanup_test_project(async_client, data["id"])

    async def test_create_project_empty_name(self, async_client: AsyncClient):
        """Test project creation with empty name (should use default)."""
        response = await async_client.post("/api/creation/projects", json={"name": ""})

        # API should accept empty name and use default
        assert response.status_code == 200
        data = response.json()

        # Cleanup
        await cleanup_test_project(async_client, data["id"])

    async def test_create_multiple_projects(self, async_client: AsyncClient):
        """Test creating multiple projects sequentially."""
        created_ids = []

        for i in range(3):
            response = await async_client.post(
                "/api/creation/projects",
                json={"name": f"Test Project {i}"}
            )
            assert response.status_code == 200
            data = response.json()
            created_ids.append(data["id"])

        # Verify all projects are created with unique IDs
        assert len(set(created_ids)) == 3

        # Cleanup
        for project_id in created_ids:
            await cleanup_test_project(async_client, project_id)


class TestProjectListing:
    """Tests for project listing."""

    async def test_list_projects_empty(self, async_client: AsyncClient):
        """Test listing when no projects exist."""
        response = await async_client.get("/api/creation/projects")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        # May have existing projects from other tests

    async def test_list_projects_with_data(self, async_client: AsyncClient):
        """Test listing projects with created data."""
        # Create test projects
        created_ids = []
        for i in range(2):
            project = await create_test_project(async_client, f"List Test {i}")
            created_ids.append(project["id"])

        # List projects
        response = await async_client.get("/api/creation/projects")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 2

        # Verify projects are sorted by updated_at descending
        items = data["items"]
        if len(items) >= 2:
            # Recent projects should be at the top
            created_in_response = [item["id"] for item in items]
            assert all(pid in created_in_response for pid in created_ids)

        # Cleanup
        for project_id in created_ids:
            await cleanup_test_project(async_client, project_id)

    async def test_list_projects_pagination(self, async_client: AsyncClient):
        """Test project listing with pagination parameters."""
        # Create multiple projects
        created_ids = []
        for i in range(5):
            project = await create_test_project(async_client, f"Page Test {i}")
            created_ids.append(project["id"])

        # Test limit
        response = await async_client.get("/api/creation/projects?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2

        # Test offset
        response = await async_client.get("/api/creation/projects?offset=1&limit=2")
        assert response.status_code == 200

        # Cleanup
        for project_id in created_ids:
            await cleanup_test_project(async_client, project_id)


class TestProjectContent:
    """Tests for project content management."""

    async def test_get_project_content(self, async_client: AsyncClient, sample_content: str):
        """Test getting project content."""
        # Create project
        project = await create_test_project(async_client, "Content Test")

        # Update content first
        await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": sample_content}
        )

        # Get content
        response = await async_client.get(f"/api/creation/projects/{project['id']}/content")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project["id"]
        assert data["name"] == "Content Test"
        assert "content" in data
        assert "updated_at" in data

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_get_project_content_empty(self, async_client: AsyncClient):
        """Test getting content of newly created project (should be empty)."""
        # Create project
        project = await create_test_project(async_client, "Empty Content Test")

        # Get content
        response = await async_client.get(f"/api/creation/projects/{project['id']}/content")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == ""  # New project should have empty content

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_update_project_content(self, async_client: AsyncClient, sample_content: str):
        """Test updating project content."""
        # Create project
        project = await create_test_project(async_client, "Update Content Test")

        # Update content
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": sample_content}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "保存成功"
        assert "updated_at" in data

        # Verify content was saved
        get_response = await async_client.get(f"/api/creation/projects/{project['id']}/content")
        assert get_response.json()["content"] == sample_content

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_update_content_with_markdown(self, async_client: AsyncClient):
        """Test updating project content with markdown formatting."""
        markdown_content = """# Main Title

## Section 1
Content with **bold** and *italic* text.

### Subsection
- Item 1
- Item 2

```python
def hello():
    print("Hello, World!")
```

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
"""
        # Create project
        project = await create_test_project(async_client, "Markdown Test")

        # Update content
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": markdown_content}
        )

        assert response.status_code == 200

        # Verify content
        get_response = await async_client.get(f"/api/creation/projects/{project['id']}/content")
        assert get_response.json()["content"] == markdown_content

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_update_content_with_chinese(self, async_client: AsyncClient):
        """Test updating project content with Chinese characters."""
        chinese_content = """# 工艺文件标题

## 工序说明
1. 首先进行材料准备
2. 然后进行加工
3. 最后进行检验

### 技术要求
- 精度要求：±0.01mm
- 表面粗糙度：Ra 1.6
"""
        # Create project
        project = await create_test_project(async_client, "中文内容测试")

        # Update content
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": chinese_content}
        )

        assert response.status_code == 200

        # Verify content
        get_response = await async_client.get(f"/api/creation/projects/{project['id']}/content")
        assert get_response.json()["content"] == chinese_content

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_update_content_large(self, async_client: AsyncClient):
        """Test updating project with large content."""
        # Create large content (100KB+)
        large_content = "# Large Document\n\n" + ("This is a test line.\n" * 5000)

        # Create project
        project = await create_test_project(async_client, "Large Content Test")

        # Update content
        response = await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": large_content}
        )

        assert response.status_code == 200

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_multiple_content_updates(self, async_client: AsyncClient):
        """Test multiple sequential content updates."""
        # Create project
        project = await create_test_project(async_client, "Multiple Updates Test")

        # Perform multiple updates
        contents = [
            "First content",
            "Second content with more text",
            "Third content - final version"
        ]

        for content in contents:
            response = await async_client.put(
                f"/api/creation/projects/{project['id']}/content",
                json={"content": content}
            )
            assert response.status_code == 200

        # Verify final content
        get_response = await async_client.get(f"/api/creation/projects/{project['id']}/content")
        assert get_response.json()["content"] == contents[-1]

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestProjectDeletion:
    """Tests for project deletion."""

    async def test_delete_project_success(self, async_client: AsyncClient):
        """Test successful project deletion."""
        # Create project
        project = await create_test_project(async_client, "Delete Test")

        # Delete project
        response = await async_client.delete(f"/api/creation/projects/{project['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "删除成功"

        # Verify project is deleted (should return 404)
        get_response = await async_client.get(f"/api/creation/projects/{project['id']}/content")
        assert get_response.status_code == 404

    async def test_delete_project_with_content(self, async_client: AsyncClient, sample_content: str):
        """Test deleting project with content."""
        # Create project and add content
        project = await create_test_project(async_client, "Delete With Content")
        await async_client.put(
            f"/api/creation/projects/{project['id']}/content",
            json={"content": sample_content}
        )

        # Delete project
        response = await async_client.delete(f"/api/creation/projects/{project['id']}")

        assert response.status_code == 200

    async def test_delete_nonexistent_project(self, async_client: AsyncClient):
        """Test deleting a non-existent project."""
        response = await async_client.delete("/api/creation/projects/999999")

        assert response.status_code == 404

    async def test_delete_project_twice(self, async_client: AsyncClient):
        """Test deleting the same project twice."""
        # Create project
        project = await create_test_project(async_client, "Double Delete Test")

        # First delete
        response = await async_client.delete(f"/api/creation/projects/{project['id']}")
        assert response.status_code == 200

        # Second delete (should fail)
        response = await async_client.delete(f"/api/creation/projects/{project['id']}")
        assert response.status_code == 404


class TestProjectVersions:
    """Tests for project version management."""

    async def test_get_versions_empty(self, async_client: AsyncClient):
        """Test getting versions for new project."""
        # Create project
        project = await create_test_project(async_client, "Version Test")

        # Get versions (should be empty)
        response = await async_client.get(f"/api/creation/projects/{project['id']}/versions")

        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert isinstance(data["versions"], list)

        # Cleanup
        await cleanup_test_project(async_client, project["id"])


class TestProjectMaterials:
    """Tests for project material management."""

    async def test_get_project_materials_empty(self, async_client: AsyncClient):
        """Test getting materials for project with no materials."""
        # Create project
        project = await create_test_project(async_client, "Materials Test")

        # Get materials
        response = await async_client.get(f"/api/creation/projects/{project['id']}/materials")

        assert response.status_code == 200
        data = response.json()
        assert "searches" in data
        assert "documents" in data
        assert data["searches"] == []
        assert data["documents"] == []

        # Cleanup
        await cleanup_test_project(async_client, project["id"])

    async def test_get_available_materials(self, async_client: AsyncClient):
        """Test getting available materials list."""
        response = await async_client.get("/api/creation/materials")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
