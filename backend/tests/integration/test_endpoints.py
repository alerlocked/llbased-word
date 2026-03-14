"""
API端点集成测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app  # 假设main.py在app目录下


@pytest.mark.integration
class TestAPIEndpoints:
    """API端点集成测试类"""

    def setup_method(self):
        """设置测试客户端"""
        self.client = TestClient(app)

    def test_health_check(self):
        """测试健康检查端点"""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_api_docs_accessible(self):
        """测试API文档可访问"""
        response = self.client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema(self):
        """测试OpenAPI模式"""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"