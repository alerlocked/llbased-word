# Implementation Plan: PDF Image Understanding and Extraction Feature

## Overview

为PDF解析系统添加图片理解(image understanding)和图片提取(image extraction)功能，以完整捕获工艺文件中的流程图、示意图等视觉内容，避免信息缺失。

当前系统已经能够：
- 提取表格结构（HTML格式，保留colspan/rowspan）
- 提取文本内容（Markdown格式）
- MinerU VLM已提取44张图片到images目录

缺失的功能：
- 图片与页面的关联信息
- 图片内容的语义理解（流程图、示意图等）
- 图片描述文本生成
- 图片在输出中的整合展示

## Requirements Summary

1. **图片提取增强**: 从PDF中提取图片并建立与页面的关联
2. **图片理解**: 使用VLM理解图片内容（流程图、示意图、表格图像等）
3. **内容整合**: 将图片及其描述整合到输出中（HTML/Markdown）
4. **元数据管理**: 记录图片的位置、类型、描述等信息
5. **单文件输出**: 一个PDF对应一个完整的HTML文件，包含所有44页内容（表格+图片+描述），便于与原PDF逐页对比

## Research Findings

### Best Practices

1. **MinerU内置图片提取**
   - MinerU VLM已自动提取图片到`images/`目录
   - `content_list.json`中记录了图片路径和bbox信息
   - 支持图片与caption/footnote的自动配对

2. **VLM图片理解方案**
   - **Qwen2-VL/Qwen3-VL**: 开源视觉语言模型，支持流程图理解
   - **GPT-4V/GPT-4o**: 商业API，高精度图像理解
   - **GLM-4V-9B**: MinerU内置VLM模型

3. **图片类型分类**
   - 流程图(Flowchart): 工艺流程、决策流程
   - 示意图(Diagram): 结构示意、装配示意
   - 表格图像(Table Image): 表格的视觉快照
   - 普通图片(Photo): 实物照片

### Reference Implementations

1. **MinerU VLM Backend** - [GitHub: opendatalab/MinerU](https://github.com/opendatalab/MinerU)
   - `mineru/backend/vlm/vlm_analyze.py` - VLM分析核心
   - `mineru/backend/vlm/model_output_to_middle_json.py` - 输出转换

2. **PyMuPDF Image Extraction** - 现有代码
   - `backend/app/tools/pdf_parser.py:_extract_image_blocks()`

3. **QwenVL Flowchart Understanding** - [CSDN Blog](https://m.blog.csdn.net/weixin_30533301/article/details/155471476)
   - PyMuPDF + PIL提取图片
   - QwenVL分析流程图结构

### Technology Decisions

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 图片提取 | 复用MinerU已有提取 | MinerU已提取44张图片到images/，无需重复 |
| VLM理解 | GLM-4V/Qwen2-VL本地模型 | 与MinerU VLM保持一致，支持GPU加速 |
| 输出格式 | **单个HTML文件** | 一个PDF对应一个HTML，便于与原PDF逐页对比 |
| 存储结构 | 扁平化输出 | `{PDF名称}_complete.html` + `images/` 目录 |

## Implementation Tasks

### Phase 1: 图片元数据提取

**1.1 理解MinerU输出结构**
- Description: MinerU提取的是**表格整体截图**（44张），不是单独图片
- content_list.json中的元素类型：
  - `table` (44个): 表格内容，包含HTML结构、表格截图路径
  - `footer` (1个): 第1页的页脚"共53页第1页"
  - `page_number` (43个): 各页页码"第2页"、"第3页"等
- Files to analyze:
  - `data/exports_vlm_full/全单电缆装配规程/vlm/全单电缆装配规程_content_list.json`
  - `data/exports_vlm_full/全单电缆装配规程/vlm/images/` 目录

**1.2 提取表格截图元数据**
- Description: 从content_list.json提取表格及其截图信息
- Files to modify:
  - `run_full_pdf_extraction.py` - 添加`extract_table_image_metadata()`
- Dependencies: Task 1.1
- 代码示例:
```python
def extract_table_image_metadata(content_list: list) -> list:
    """提取表格截图元数据（MinerU只提取表格整体截图，没有单独的图片）"""
    table_images = []
    for item in content_list:
        if item.get("type") == "table" and item.get("img_path"):
            table_images.append({
                "page": item.get("page_idx", -1) + 1,
                "table_img_path": item.get("img_path", ""),  # 表格整体截图
                "bbox": item.get("bbox", []),
                "caption": item.get("table_caption", []),
                "has_inner_image": False,  # 后续VLM判断是否包含流程图等图片
            })
    return table_images
```

**1.3 创建图片信息汇总**
- Description: 生成`image_info.json`汇总所有表格截图信息
- Files to modify:
  - `run_full_pdf_extraction.py` - 在`process_mineru_output()`中添加
- Dependencies: Task 1.2

### Phase 2: 表格截图分析与图片提取

**2.1 检测表格内是否包含流程图/图片**
- Description: 用VLM分析表格截图，判断是否包含非文字图形元素
- 判断标准:
  - 是否有方框+箭头组成的流程图
  - 是否有示意图、装配图
  - 是否为纯文字表格
- Files to create:
  - `backend/app/tools/image_understanding.py` - 图片理解工具
- Dependencies: Phase 1完成
- 代码框架:
```python
class TableImageAnalyzer:
    """表格截图分析器"""

    def detect_inner_image(self, table_img_path: str) -> dict:
        """检测表格内是否包含流程图等图片元素"""
        return {
            "has_inner_image": True/False,
            "image_type": "flowchart" / "diagram" / "pure_table",
            "inner_image_bbox": [x, y, w, h],  # 如果有图片，返回其在表格截图中的位置
            "description": "工艺流程图，包含5个步骤"
        }
```

**2.2 从表格截图中裁剪内部图片**
- Description: 如果表格包含流程图，裁剪出图片区域单独保存
- Files to modify:
  - `run_full_pdf_extraction.py` - 添加`extract_inner_images()`
- Dependencies: Task 2.1
- 输出:
  - `data/exports_vlm_full/inner_images/page8_flowchart.jpg` - 第8页的流程图
  - `data/exports_vlm_full/inner_images/inner_images_info.json` - 内部图片元数据
- 代码示例:
```python
def extract_inner_images(table_images: list, output_dir: Path) -> list:
    """从表格截图中提取内部图片（流程图等）"""
    inner_images = []
    analyzer = TableImageAnalyzer()

    for table in table_images:
        result = analyzer.detect_inner_image(table["table_img_path"])
        if result["has_inner_image"] and result["image_type"] in ["flowchart", "diagram"]:
            # 裁剪内部图片
            img = Image.open(table["table_img_path"])
            bbox = result["inner_image_bbox"]
            cropped = img.crop(bbox)

            # 保存
            inner_path = output_dir / f"inner_images/page{table['page']}_{result['image_type']}.jpg"
            cropped.save(inner_path)

            inner_images.append({
                "source_table": table["index"],
                "page": table["page"],
                "type": result["image_type"],
                "path": str(inner_path),
                "description": result["description"]
            })

    return inner_images
```

**2.3 VLM图片内容理解**
- Description: 对提取的内部图片进行深度理解
- Files to modify:
  - `backend/app/tools/image_understanding.py` - 添加深度分析方法
- Dependencies: Task 2.2
- 输出: 图片的详细描述、步骤列表、连接关系

### Phase 3: 输出整合（单文件HTML）

**3.1 生成单个完整HTML文件**
- Description: 一个PDF对应一个HTML文件，包含所有44页的表格、图片和描述
- Files to modify:
  - `run_full_pdf_extraction.py` - 重构为生成单个HTML
- Dependencies: Phase 2完成
- 删除: 不再生成 `html_tables/table_X_pageY.html` 分散文件
- 输出: `data/exports_vlm_full/{PDF名称}_complete.html`
- HTML结构:
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>全单电缆装配规程 - 完整解析</title>
  <style>
    /* 完整CSS样式 */
    body { font-family: "Microsoft YaHei", Arial, sans-serif; }
    .page-break { page-break-after: always; }
    .page-section { margin-bottom: 50px; border-bottom: 1px dashed #ccc; padding-bottom: 30px; }
    .table-container { overflow-x: auto; }
    .image-container { margin: 20px 0; }
    .image-container img { max-width: 100%; border: 1px solid #ddd; }
    .description { background: #f9f9f9; padding: 10px; margin-top: 10px; }
    nav { position: fixed; top: 0; right: 0; background: #333; color: white; padding: 10px; }
    nav a { color: white; margin: 0 5px; }
  </style>
</head>
<body>
  <!-- 页面导航 -->
  <nav>
    <a href="#page-1">第1页</a>
    <a href="#page-2">第2页</a>
    ... (所有44页链接)
  </nav>

  <h1>全单电缆装配规程 - 完整解析报告</h1>
  <p>共44页 | 生成时间: 2026-02-24</p>

  <!-- 第1页 -->
  <section id="page-1" class="page-section">
    <h2>第1页</h2>
    <div class="table-container">
      <table>...表格HTML...</table>
    </div>
    <div class="image-container">
      <img src="images/xxx.jpg" alt="表格快照">
      <p class="description">表格类型: 封面页</p>
    </div>
  </section>

  <!-- 第8页（流程图） -->
  <section id="page-8" class="page-section">
    <h2>第8页 - 工艺流程图</h2>
    <div class="table-container">
      <table>...表格HTML...</table>
    </div>
    <div class="image-container">
      <h3>流程图理解</h3>
      <img src="images/5054035...jpg" alt="工艺流程图">
      <p class="description">流程说明: 装前准备 → 安装密封圈2 → 安装行程延时开关组合 → 四五舱对接 → 五舱装配</p>
      <div class="flowchart-steps">
        <ol>
          <li>装前准备</li>
          <li>安装密封圈2</li>
          <li>安装行程延时开关组合</li>
          <li>四五舱对接</li>
          <li>五舱装配</li>
        </ol>
      </div>
    </div>
  </section>

  <!-- ... 第9-44页 ... -->

</body>
</html>
```

**3.2 Markdown输出（可选）**
- Description: 同时生成Markdown版本，便于编辑
- Files to modify:
  - `run_full_pdf_extraction.py` - 添加Markdown生成
- Dependencies: Task 3.1
- 输出: `data/exports_vlm_full/{PDF名称}_complete.md`

### Phase 4: 后端服务集成

**4.1 API端点扩展**
- Description: 添加图片理解相关的API端点
- Files to modify:
  - `backend/app/api/pdf_routes.py` - 添加路由
  - `backend/app/tools/image_understanding.py` - 实现逻辑
- Dependencies: Phase 2完成
- API设计:
```
POST /api/pdf/extract-with-images
  - 上传PDF，返回表格+图片+描述

GET /api/pdf/{doc_id}/images
  - 获取文档的所有图片及描述

POST /api/image/analyze
  - 分析单张图片，返回类型和描述
```

**4.2 配置更新**
- Description: 更新配置以支持图片理解功能
- Files to modify:
  - `backend/app/shared/config.py` - 添加IMAGE_CONFIG
- Dependencies: 无
- 配置项:
```python
IMAGE_CONFIG = {
    "enable_understanding": True,
    "vlm_model": "glm-4v-9b",  # 或 qwen2-vl, gpt-4v
    "batch_size": 8,
    "output_format": "html",  # html, markdown, json
    "include_captions": True,
    "classify_types": True,
}
```

## Codebase Integration Points

### Files to Modify

| 文件路径 | 修改内容 |
|---------|---------|
| `run_full_pdf_extraction.py` | 添加图片提取和理解逻辑 |
| `backend/app/shared/config.py` | 添加IMAGE_CONFIG配置 |
| `backend/app/tools/pdf_parser.py` | 集成图片理解到解析流程 |
| `backend/app/api/pdf_routes.py` | 添加图片相关API端点 |

### New Files to Create

| 文件路径 | 用途 |
|---------|------|
| `backend/app/tools/image_understanding.py` | VLM图片理解工具类 |
| `data/exports_vlm_full/{PDF名称}_complete.html` | **单个完整HTML文件**（包含所有44页的表格+图片+描述） |
| `data/exports_vlm_full/{PDF名称}_complete.md` | Markdown版本（可选） |
| `data/exports_vlm_full/image_info.json` | 图片元数据汇总 |

### Files to Remove/Deprecate

| 文件路径 | 原因 |
|---------|------|
| `data/exports_vlm_full/html_tables/` | 不再需要分散的每页HTML文件 |
| `data/exports_vlm_full/all_tables_combined.html` | 被 `{PDF名称}_complete.html` 替代 |

### Existing Patterns to Follow

1. **MinerU调用模式**: 参考`run_full_pdf_extraction.py`中的`extract_with_mineru_vlm()`
2. **配置管理模式**: 参考`config.py`中的`MINERU_CONFIG`
3. **输出处理模式**: 参考`process_mineru_output()`的处理流程

## Technical Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    PDF解析系统架构                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────────┐    │
│  │ PDF文件 │───►│ MinerU VLM  │───►│ content_list.json│    │
│  └─────────┘    └─────────────┘    └────────┬────────┘    │
│                                              │              │
│                     ┌────────────────────────┼──────────┐  │
│                     │                        │          │  │
│                     ▼                        ▼          ▼  │
│              ┌──────────┐            ┌──────────┐ ┌─────┐ │
│              │ 表格处理  │            │ 图片处理  │ │文本 │ │
│              └────┬─────┘            └────┬─────┘ └──┬──┘ │
│                   │                       │          │    │
│                   │              ┌────────┴────────┐ │    │
│                   │              │                 │ │    │
│                   │              ▼                 │ │    │
│                   │      ┌───────────────┐        │ │    │
│                   │      │ VLM图片理解   │        │ │    │
│                   │      │ (GLM-4V/Qwen) │        │ │    │
│                   │      └───────┬───────┘        │ │    │
│                   │              │                │ │    │
│                   └──────────────┼────────────────┴─┘    │
│                                  │                        │
│                                  ▼                        │
│                       ┌────────────────────┐             │
│                       │   输出生成器       │             │
│                       └─────────┬──────────┘             │
│                                 │                        │
│              ┌──────────────────┼──────────────────┐     │
│              │                  │                  │     │
│              ▼                  ▼                  ▼     │
│      ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│      │ all_tables.  │  │ full_report. │  │ image_info │ │
│      │ combined.html│  │ html         │  │ .json      │ │
│      └──────────────┘  └──────────────┘  └────────────┘ │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. PDF输入 → MinerU VLM解析
2. content_list.json → 分类(表格/图片/文本)
3. 图片 → VLM理解 → 类型+描述
4. 合并输出 → HTML/Markdown/JSON
```

### Image Understanding Pipeline

```
图片输入
    │
    ▼
┌─────────────────┐
│ 图片预处理      │ → 调整尺寸、格式转换
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ VLM分析         │ → GLM-4V/Qwen2-VL推理
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 结果解析        │ → 类型分类、描述生成
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 结构化输出      │ → JSON格式结果
└─────────────────┘
```

## Dependencies and Libraries

| 库/依赖 | 版本 | 用途 |
|--------|------|------|
| `torch` | 2.12+ | VLM推理 |
| `transformers` | 4.40+ | VLM模型加载 |
| `Pillow` | 10.0+ | 图片处理 |
| `PyMuPDF` | 1.24+ | PDF图片提取（备选） |
| `beautifulsoup4` | 4.12+ | HTML解析 |

## Testing Strategy

### Unit Tests
- `test_image_extraction.py`: 测试图片元数据提取
- `test_image_understanding.py`: 测试VLM图片理解
- `test_output_generation.py`: 测试HTML/Markdown生成

### Integration Tests
- 完整PDF解析流程（表格+图片）
- API端点功能测试

### Edge Cases to Cover
1. 无图片的PDF文档
2. 图片密集型页面
3. 流程图vs示意图的分类
4. 图片caption缺失的情况
5. GPU内存不足时的降级处理

## Success Criteria

- [ ] 能够从content_list.json提取所有图片元数据
- [ ] 能够使用VLM理解图片内容（流程图、示意图等）
- [ ] 生成的HTML包含图片及其描述
- [ ] 生成的Markdown包含图片引用和说明
- [ ] 图片类型正确分类（流程图/示意图/表格图像/照片）
- [ ] 第8页流程图完整理解（步骤、连接关系）
- [ ] 处理时间可接受（单页<30秒）
- [ ] GPU内存使用合理（<8GB）

## Notes and Considerations

### 重要注意事项

1. **VLM模型选择**
   - 推荐: GLM-4V-9B（与MinerU一致）
   - 备选: Qwen2-VL-7B（开源，中文友好）
   - 商业: GPT-4V（高精度，需API密钥）

2. **性能优化**
   - 批处理图片减少模型加载开销
   - 缓存已处理的图片描述
   - 可选择性启用图片理解

3. **输出格式选择**
   - HTML: 最佳可视化效果
   - Markdown: 便于编辑和版本控制
   - JSON: 便于程序处理

### 潜在挑战

1. 流程图箭头和连接线的准确识别
2. 中文工艺术语的准确描述
3. GPU显存限制（大图片处理）
4. 处理时间（44张图片可能需要额外10-20分钟）

### 未来增强

1. 支持更多图片类型（电路图、机械图等）
2. 图片内容搜索功能
3. 图片间关系分析
4. 自动生成工艺步骤清单

---

*创建时间: 2026-02-24*
*相关文件: `run_full_pdf_extraction.py`, `backend/app/shared/config.py`*
*参考文档: [MinerU GitHub](https://github.com/opendatalab/MinerU), [QwenVL](https://m.blog.csdn.net/weixin_30533301/article/details/155471476)*
