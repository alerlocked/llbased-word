# Bug Fix: MinerU VLM 后端失败问题

**状态**: 待修复  
**优先级**: 高（影响性能，用户每页 OCR 都失败）  
**日期**: 2026-03-22  
**作者**: Plan Agent

---

## 问题描述

### 现象
- PDF 解析时 MinerU OCR 每页都失败（`mineru_ocr_failed`）
- 系统自动 fallback 到 Qwen-VL，速度慢 3-5 倍
- 预期性能：5-10 秒/页，实际 fallback 后：20-50 秒/页

### 根本原因

**错误的 MinerU VLM 调用方式**：

`backend/app/services/vl_service.py` 中的 `_mineru_image_to_markdown_sync` 方法使用了错误的方式：

1. **错误路径**：
   ```python
   # 当前代码（错误）
   from app.tools.table_extractors.mineru_extractor import MinerUTableExtractor
   from mineru.cli.common import do_parse
   
   # 将图片转换为 PDF（低效且容易失败）
   pdf_bytes = img2pdf.convert(img_f.read())
   
   # 调用 CLI 接口（不是 VLM 后端的正确 API）
   do_parse(output_dir, pdf_file_names, pdf_bytes_list, ...)
   ```

2. **为什么会失败**：
   - `do_parse` 是 CLI 工具的高层封装，不直接支持图像输入
   - 图片转 PDF 的过程容易失败（`img2pdf` 可能不兼容某些格式）
   - 这不是 MinerU 2.7.6 VLM 后端的正确用法

3. **正确的 MinerU 2.7.6 VLM API**（位于 `mineru/backend/vlm/vlm_analyze.py`）：
   ```python
   from mineru.backend.vlm.vlm_analyze import ModelSingleton
   from PIL import Image
   
   # 获取 VLM 模型（单例模式）
   predictor = ModelSingleton().get_model(
       backend="transformers",  # 或 "vllm-engine", "lmdeploy-engine", "http-client"
       model_path=None,  # 自动下载
       server_url=None,
   )
   
   # 方法1：单张图片
   result: list[ContentBlock] = predictor.two_step_extract(image_pil)
   
   # 方法2：批量图片
   results: list[list[ContentBlock]] = predictor.batch_two_step_extract(images_pil_list)
   ```

4. **`ContentBlock` 结构**：
   ```python
   ContentBlock(
       type: str,      # "text", "title", "table", "image", "equation", "code"
       bbox: list,     # [x1, y1, x2, y2]
       angle: int,     # None, 0, 90, 180, 270
       content: str,   # 文本内容或表格 HTML
   )
   ```

---

## 修复方案

### 核心改动

#### 1. 新增：`_init_mineru_vlm()` - 初始化 MinerU VLM 客户端

```python
def _init_mineru_backend(self):
    """初始化 MinerU VLM 后端"""
    try:
        from mineru.backend.vlm.vlm_analyze import ModelSingleton
        
        # 获取配置
        backend = settings.MINERU_BACKEND  # "transformers" 或其他
        
        # 获取 VLM 模型（单例模式，自动下载模型）
        self._mineru_predictor = ModelSingleton().get_model(
            backend=backend,
            model_path=None,  # 自动下载
            server_url=None,
        )
        
        self._mineru_available = True
        logger.info("mineru_vlm_initialized", backend=backend)
        
    except ImportError as e:
        logger.error("mineru_vlm_import_failed", error=str(e))
        if self.fallback_to_qwen:
            self.backend = "qwen"
            self._init_qwen_backend()
        else:
            raise ImportError("MinerU VLM 未安装，请运行: pip install mineru[all] mineru-vl-utils")
    except Exception as e:
        logger.error("mineru_vlm_init_failed", error=str(e))
        if self.fallback_to_qwen:
            self.backend = "qwen"
            self._init_qwen_backend()
        else:
            raise
```

#### 2. 替换：`_ocr_with_mineru()` - 使用正确的 VLM API

```python
async def _ocr_with_mineru(self, image_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
    """
    使用 MinerU VLM 进行 OCR（正确方式）
    """
    start_time = time.time()
    
    if not self._mineru_available or not self._mineru_predictor:
        raise RuntimeError("MinerU VLM 后端不可用")
    
    try:
        logger.debug("mineru_vlm_ocr_started", image=image_path.name)
        
        # 加载图片
        from PIL import Image
        image_pil = Image.open(image_path).convert("RGB")
        
        # 调用 MinerU VLM API
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            content_blocks = await loop.run_in_executor(
                executor,
                self._mineru_predictor.two_step_extract,
                image_pil
            )
        
        # 转换 ContentBlock 为 Markdown
        markdown_content = self._content_blocks_to_markdown(content_blocks)
        
        # 提取图表信息
        figures = self._extract_figures_from_blocks(content_blocks)
        
        duration_ms = (time.time() - start_time) * 1000
        log_api_call("MinerU-VLM", "OCR", "success", duration_ms)
        
        return markdown_content, figures
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_api_call("MinerU-VLM", "OCR", "error", duration_ms)
        logger.error("mineru_vlm_ocr_failed", image=image_path.name, error=str(e))
        raise
```

#### 3. 新增：`_content_blocks_to_markdown()` - 转换为 Markdown

```python
def _content_blocks_to_markdown(self, content_blocks: list) -> str:
    """
    将 MinerU ContentBlock 列表转换为 Markdown
    
    Args:
        content_blocks: MinerU VLM 返回的内容块列表
    
    Returns:
        Markdown 文本
    """
    md_parts = []
    
    for block in content_blocks:
        block_type = block.type
        content = block.content or ""
        bbox = block.bbox
        
        if block_type == "title":
            # 标题
            md_parts.append(f"\n# {content}\n")
        
        elif block_type in ["text", "list"]:
            # 普通文本
            md_parts.append(f"\n{content}\n")
        
        elif block_type == "table":
            # 表格（content 已是 HTML 格式）
            md_parts.append(f"\n{content}\n")
        
        elif block_type == "equation":
            # 公式
            md_parts.append(f"\n$$\n{content}\n$$\n")
        
        elif block_type == "code":
            # 代码块
            md_parts.append(f"\n```\n{content}\n```\n")
        
        elif block_type == "image":
            # 图片标记（图片本身会在 figures 中处理）
            md_parts.append(f"\n[图片: {bbox}]\n")
        
        else:
            # 未知类型，作为文本处理
            if content:
                md_parts.append(f"\n{content}\n")
    
    return "\n".join(md_parts)
```

#### 4. 新增：`_extract_figures_from_blocks()` - 提取图表

```python
def _extract_figures_from_blocks(self, content_blocks: list) -> List[Dict[str, Any]]:
    """
    从 ContentBlock 中提取图表信息
    
    Args:
        content_blocks: MinerU VLM 返回的内容块列表
    
    Returns:
        图表信息列表
    """
    figures = []
    
    for block in content_blocks:
        if block.type == "table":
            figures.append({
                "type": "table",
                "caption": "",
                "description": block.content or "",
                "bbox": block.bbox,
            })
        
        elif block.type == "image":
            figures.append({
                "type": "image",
                "caption": "",
                "description": "",
                "bbox": block.bbox,
            })
    
    return figures
```

#### 5. 删除：不再需要的方法

- `_mineru_image_to_markdown()` - 删除
- `_mineru_image_to_markdown_sync()` - 删除
- `_extract_figures_with_mineru()` - 删除
- `_init_mineru_backend()` 中的 `MinerUTableExtractor` 相关代码 - 删除

#### 6. 更新：`get_backend_info()` - 添加 VLM 信息

```python
def get_backend_info(self) -> Dict[str, Any]:
    """获取当前后端信息"""
    info = {
        "current_backend": self.backend,
        "max_workers": self.max_workers,
        "fallback_to_qwen": self.fallback_to_qwen,
        "available_backends": ["qwen"],
    }
    
    if self._mineru_available:
        info["available_backends"].insert(0, "mineru")
        info["mineru_info"] = {
            "type": "vlm",
            "backend": settings.MINERU_BACKEND,
            "initialized": self._mineru_predictor is not None,
        }
    
    info["qwen_info"] = {
        "model": getattr(self, 'qwen_model', 'qwen-vl-max'),
        "initialized": self._qwen_initialized
    }
    
    return info
```

---

## 配置检查

### 需要确认的配置项

`backend/app/config.py`:

```python
# MinerU 配置
MINERU_BACKEND: str = "transformers"  # 或 "vllm-engine", "lmdeploy-engine"
MINERU_TABLE_MODEL: str = "default"
MINERU_LANG: str = "ch"
```

### 依赖检查

```bash
# 必需的包
pip install mineru[all]
pip install mineru-vl-utils  # 提供 MinerUClient
```

---

## 测试验证

### 1. 单元测试

```python
# tests/test_vl_service_mineru.py
import pytest
from pathlib import Path
from PIL import Image

def test_mineru_vlm_ocr():
    """测试 MinerU VLM OCR"""
    from app.services.vl_service import VLService
    
    service = VLService(backend="mineru")
    
    # 测试图片
    test_image = Path("tests/fixtures/sample_page.jpg")
    
    # 执行 OCR
    markdown, figures = await service.ocr_page_to_markdown(test_image)
    
    # 验证
    assert len(markdown) > 0, "Markdown 内容为空"
    assert "mineru_ocr_failed" not in markdown, "OCR 失败"
    
    print(f"✅ MinerU VLM OCR 成功")
    print(f"   内容长度: {len(markdown)}")
    print(f"   图表数量: {len(figures)}")
```

### 2. 集成测试

```bash
# 测试完整 PDF 解析流程
cd backend
python -m pytest tests/test_pdf_parsing.py -v -k "mineru"
```

### 3. 性能测试

```python
# 测试性能对比
import time

async def benchmark_ocr():
    service = VLService(backend="mineru")
    test_image = Path("tests/fixtures/sample_page.jpg")
    
    start = time.time()
    markdown, figures = await service.ocr_page_to_markdown(test_image)
    duration = time.time() - start
    
    print(f"MinerU VLM: {duration:.2f}s")
    assert duration < 15, f"性能不达标: {duration:.2f}s > 15s"
```

---

## 风险评估

### 低风险
- ✅ 只修改 `vl_service.py`，不涉及其他模块
- ✅ 保持相同的接口（`ocr_page_to_markdown`）
- ✅ 有 fallback 机制（Qwen-VL）

### 需要注意
- ⚠️ 首次运行需要下载 VLM 模型（可能较大）
- ⚠️ `mineru-vl-utils` 包版本兼容性

---

## 回滚方案

如果修复后出现问题：

1. **快速回滚**：
   ```bash
   git revert <commit-hash>
   ```

2. **配置回退**：
   ```bash
   # 临时禁用 MinerU，强制使用 Qwen
   export VL_SERVICE_BACKEND=qwen
   ```

---

## 相关文件

### 需要修改
- `backend/app/services/vl_service.py` - 主要修改文件

### 需要删除
- 不再需要 `img2pdf` 依赖

### 可能需要更新
- `backend/app/config.py` - 确认 MINERU_BACKEND 配置
- `backend/requirements.txt` - 确保 `mineru-vl-utils` 已添加

---

## 参考文档

### MinerU 2.7.6 VLM API
- 位置: `C:\Users\alerl\AppData\Roaming\Python\Python313\site-packages\mineru\backend\vlm\vlm_analyze.py`
- 核心类: `ModelSingleton`, `MinerUClient`
- 核心方法: `two_step_extract`, `batch_two_step_extract`

### ContentBlock 结构
```python
from mineru_vl_utils.structs import ContentBlock

ContentBlock(
    type: str,      # "text", "title", "table", "image", "equation", "code"
    bbox: list,     # [x1, y1, x2, y2]
    angle: int,     # None, 0, 90, 180, 270
    content: str,   # 文本内容或表格 HTML
)
```

---

## 执行步骤

### Phase 1: 准备工作
1. ✅ 确认 MinerU 2.7.6 已安装
2. ✅ 确认 `mineru-vl-utils` 已安装
3. ✅ 备份当前 `vl_service.py`

### Phase 2: 实施修复
1. 修改 `_init_mineru_backend()` - 使用正确的初始化方式
2. 替换 `_ocr_with_mineru()` - 使用 MinerUClient API
3. 新增 `_content_blocks_to_markdown()` - 转换为 Markdown
4. 新增 `_extract_figures_from_blocks()` - 提取图表
5. 删除不再需要的方法
6. 更新 `get_backend_info()`

### Phase 3: 测试验证
1. 单元测试 - 测试单个图片 OCR
2. 集成测试 - 测试完整 PDF 解析
3. 性能测试 - 确认性能达标（5-10s/页）

### Phase 4: 上线
1. 代码审查
2. 部署到测试环境
3. 验证功能
4. 部署到生产环境

---

## 成功标准

1. ✅ MinerU OCR 不再失败（无 `mineru_ocr_failed` 错误）
2. ✅ 性能达标：5-10 秒/页
3. ✅ 不再 fallback 到 Qwen-VL
4. ✅ 所有测试通过
5. ✅ Markdown 输出质量良好

---

**预计修复时间**: 1-2 小时  
**预计测试时间**: 30 分钟  
**总预计时间**: 2-3 小时
