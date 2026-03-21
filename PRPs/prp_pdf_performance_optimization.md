# PRP: PDF 处理性能优化 - MinerU 后端 + 并行处理

## 项目
localknowledgebase-word

## 目标
将 PDF OCR 处理时间从 30 分钟降低到 3-5 分钟

## 当前问题

### 性能分析
```yaml
当前流程:
  PDF → PyMuPDF → 图片 → VLService (Qwen-VL API) → OCR
  每页: 20-50 秒
  44 页: ~30 分钟

问题:
  1. VLService 硬编码使用 Qwen-VL API
  2. 串行处理，一页一页处理
  3. API 调用延迟高
```

### 代码位置
- `backend/app/services/vl_service.py` - VLService 硬编码 Qwen-VL
- `backend/app/tools/table_extractors/mineru_extractor.py` - MinerU 已配置

## 优化方案

### 1. VLService 添加多后端支持

```python
# backend/app/services/vl_service.py

class VLService:
    def __init__(self, backend: str = "mineru"):
        """
        初始化服务
        
        Args:
            backend: 后端选择
                - "mineru": 使用 MinerU VLM（本地，5-10秒/页）
                - "qwen": 使用 Qwen-VL API（云端，20-50秒/页）
        """
        self.backend = backend
        
        if backend == "mineru":
            from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
            self.mineru = MinerUTableExtractor({"mineru_config": {"backend": "vlm-auto-engine"}})
        elif backend == "qwen":
            dashscope.api_key = settings.DASHSCOPE_API_KEY
            self.qwen_model = settings.QWEN_VL_MODEL
```

### 2. 并行处理多页

```python
# backend/app/services/vl_service.py

async def process_pages_parallel(
    self,
    image_paths: List[Path],
    max_workers: int = 4
) -> List[Dict]:
    """
    并行处理多页
    
    Args:
        image_paths: 图片路径列表
        max_workers: 最大并行数（默认 4）
    
    Returns:
        处理结果列表
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    results = []
    
    # 分批并行处理
    for i in range(0, len(image_paths), max_workers):
        batch = image_paths[i:i + max_workers]
        tasks = [self.process_page(path) for path in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(batch_results)
    
    return results
```

### 3. 配置文件更新

```python
# backend/app/config.py

class Settings(BaseSettings):
    # VLService 配置
    VL_SERVICE_BACKEND: str = "mineru"  # mineru / qwen
    VL_SERVICE_MAX_WORKERS: int = 4  # 并行处理数
    VL_SERVICE_FALLBACK_TO_QWEN: bool = True  # MinerU 失败时回退到 Qwen
```

## 任务拆分

### piv_001: VLService 多后端支持
- [ ] 添加 backend 参数
- [ ] 实现 MinerU 后端
- [ ] 实现 Qwen 后端
- [ ] 添加 fallback 逻辑

### piv_002: 并行处理
- [ ] 实现 process_pages_parallel 方法
- [ ] 限制并发数（避免内存溢出）
- [ ] 异常处理

### piv_003: 配置更新
- [ ] 添加 VL_SERVICE_BACKEND 配置
- [ ] 添加 VL_SERVICE_MAX_WORKERS 配置
- [ ] 更新 .env.example

### piv_004: 测试验证
- [ ] 单元测试：后端选择
- [ ] 单元测试：并行处理
- [ ] 集成测试：PDF 解析性能

## 验收标准

```yaml
性能:
  - 44 页处理时间 < 5 分钟（当前 30 分钟）
  - 单页处理时间 < 10 秒（当前 20-50 秒）
  - 并行处理 4 页同时

功能:
  - [ ] 支持 MinerU 后端
  - [ ] 支持 Qwen-VL 后端
  - [ ] 自动 fallback
  - [ ] 可配置后端选择

测试:
  - [ ] 单元测试通过
  - [ ] 集成测试通过
  - [ ] 性能测试通过
```

## 文件路径

```
backend/app/
  ├─ services/
  │   └─ vl_service.py          ← 修改：添加多后端 + 并行
  ├─ config.py                   ← 修改：添加配置
  └─ .env.example                ← 修改：添加配置示例
```

## 注意事项

1. MinerU 需要 GPU（检查可用性）
2. 并行数不要太高（避免内存溢出）
3. 保持向后兼容（默认行为不变）
4. 添加详细日志

## 工作目录
D:\Project Nantianmen\projects\localknowledgebase-word

## 预期效果
- 处理速度提升 6-10 倍
- 44 页文档：30 分钟 → 3-5 分钟
