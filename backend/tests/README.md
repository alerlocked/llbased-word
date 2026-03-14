# 测试框架说明

## 目录结构

根据PRPs/ai_docs/testing_guide.md规范，测试目录结构镜像源代码目录结构：

```
backend/
├── app/                    # 源代码
│   ├── api/
│   ├── agents/
│   ├── services/
│   ├── models/
│   └── utils/
└── tests/                  # 测试代码
    ├── app/               # 镜像app目录
    │   ├── api/          # 对应app/api测试
    │   ├── agents/       # 对应app/agents测试
    │   ├── services/     # 对应app/services测试
    │   ├── models/       # 对应app/models测试
    │   └── utils/        # 对应app/utils测试
    ├── integration/       # 集成测试
    └── conftest.py       # 测试配置
```

## 测试类型

### 1. 单元测试 (Unit Tests)
- 测试单个组件在隔离环境中的功能
- 使用 `@pytest.mark.unit` 标记
- 放置在对应源代码的测试目录中

### 2. 集成测试 (Integration Tests)
- 测试多个组件一起工作的功能
- 使用 `@pytest.mark.integration` 标记
- 放置在 `tests/integration/` 目录中

## 运行测试

### 运行所有测试
```bash
cd backend
uv run pytest tests/ -v
```

### 运行单元测试
```bash
uv run pytest tests/ -m unit -v
```

### 运行集成测试
```bash
uv run pytest tests/ -m integration -v
```

### 运行特定目录的测试
```bash
uv run pytest tests/app/api/ -v
```

## 测试命名规范

### 测试文件命名
- 源文件: `app/api/audio.py`
- 测试文件: `tests/app/api/test_audio.py`

### 测试函数命名
- 使用 `test_` 前缀
- 描述性名称，说明测试内容
- 示例: `test_audio_upload_success`, `test_transcribe_invalid_format`

### 测试类命名
- 使用 `Test` 前缀
- 对应被测试的类名
- 示例: `TestAudioService`, `TestTranscribeAPI`

## 测试编写指南

### 1. 保持测试简单
- 每个测试只测试一个功能
- 避免复杂的测试设置
- 使用明确的断言

### 2. 使用fixture
- 在 `conftest.py` 中定义共享fixture
- 使用适当的fixture作用域
- 避免测试间的依赖

### 3. 模拟外部依赖
- 使用 `pytest-mock` 模拟外部API调用
- 模拟数据库操作
- 模拟文件系统操作

### 4. 测试覆盖率
- 优先测试核心业务逻辑
- 测试边界条件和错误情况
- 避免过度测试简单代码

## 示例

### 单元测试示例
```python
import pytest
from app.services.audio_service import AudioService

@pytest.mark.unit
def test_audio_service_upload_success():
    """测试音频上传成功情况"""
    service = AudioService()
    result = service.validate_format("audio.mp3")
    assert result is True

@pytest.mark.unit
def test_audio_service_invalid_format():
    """测试无效音频格式"""
    service = AudioService()
    with pytest.raises(ValueError):
        service.validate_format("audio.invalid")
```

### 集成测试示例
```python
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.mark.integration
def test_audio_upload_integration():
    """测试音频上传完整流程"""
    client = TestClient(app)

    # 模拟文件上传
    files = {"file": ("test.mp3", b"fake audio data", "audio/mpeg")}
    response = client.post("/api/audio/upload", files=files)

    assert response.status_code == 200
    assert "file_id" in response.json()
```

## 注意事项

1. **测试数据**: 使用 `test_data/` 目录中的测试数据
2. **环境隔离**: 测试不应影响开发环境
3. **性能考虑**: 测试应快速执行
4. **可维护性**: 测试代码应易于理解和维护

## 下一步

1. 为每个源代码模块创建对应的测试目录
2. 编写关键模块的单元测试
3. 编写核心流程的集成测试
4. 配置CI/CD集成测试