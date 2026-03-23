# Bug Fix: PDF 上传后未自动生成 HTML

## 问题描述

### 现象
前端上传 PDF 后，OCR 完成但没有自动生成 `document.html` 和 `index.json`

### 影响
- HierarchicalContext 无法加载新文档的表格和索引
- 用户需要手动运行 `scripts/generate_document_html.py`
- 破坏了自动化工作流

### 当前状态
- ❌ 新上传的 PDF：无 document.html 和 index.json
- ✅ 历史数据（exports_vlm_full）：有完整的 HTML 和索引

---

## 根本原因分析

### 数据流断裂

**新上传流程（creation.py → document_processor.py → vl_service.py）**：
```
1. PDF → 页面图片 ✅
2. VL Service OCR → (markdown, figures) ✅
3. 保存到 MaterialPage (text_content, figures) ✅
4. 生成 content_list_v2.json ❌ 缺失
5. 调用 generate_document_html.py ❌ 缺失
```

**历史批量处理流程（MinerU）**：
```
1. PDF → content_list_v2.json ✅
2. generate_document_html.py → document.html + index.json ✅
```

### 数据格式不匹配

**VL Service 输出**：
```python
(markdown: str, figures: List[Dict])
# figures = [{"type": "chart", "caption": "...", "description": "..."}]
```

**generate_document_html.py 需要**：
```python
pages_data: List[List[Dict]]
# 每个item:
{
  "type": "table",
  "content": {
    "image_source": {"path": "images/xxx.jpg"},
    "table_caption": [{"type": "text", "content": "G4a"}],
    "html": "<table>...</table>",
    ...
  },
  "bbox": [x1, y1, x2, y2]
}
```

### 缺失的组件

1. **转换器**：将 `(markdown, figures)` 转换为 `content_list_v2.json` 格式
2. **触发器**：在上传完成后调用 `generate_document_html.py`
3. **存储路径**：确定 content_list_v2.json 的保存位置

---

## 修复方案

### 方案概述

在 `document_processor.py` 的 `process_document()` 方法中：

1. **步骤 1**：转换数据格式
   - 从 markdown 提取表格 HTML（使用正则或 markdown 解析器）
   - 构建符合 generate_document_html.py 期望的 `pages_data` 结构
   - 保存为 `content_list_v2.json`

2. **步骤 2**：调用 HTML 生成
   - 导入并调用 `generate_document_html.py` 的核心函数
   - 生成 `document.html` 和 `index.json`

3. **步骤 3**：保存到正确位置
   - 文档目录：`data/documents/{material_id}/`
   - 文件列表：
     - `content_list_v2.json`（中间数据）
     - `document.html`（最终 HTML）
     - `index.json`（语义索引）
     - `images/`（页面图片）

### 技术细节

#### 1. 数据格式转换

**输入**（VL Service 输出）：
```python
{
  "page_1": {
    "markdown": "# 标题\n\n| 列1 | 列2 |\n...",
    "figures": [
      {"type": "chart", "caption": "表格1", "description": "..."}
    ],
    "image_path": "pages/material_123_page_1.png"
  }
}
```

**输出**（content_list_v2.json）：
```python
[
  [  # 第一页
    {
      "type": "table",
      "content": {
        "image_source": {"path": "images/material_123_page_1.png"},
        "table_caption": [{"type": "text", "content": "表格1"}],
        "html": "<table><tr><th>列1</th><th>列2</th></tr>...</table>",
        "table_type": "standard_table",
        "table_nest_level": 0
      },
      "bbox": [0, 0, 0, 0]  # 简化处理，暂不提供真实bbox
    }
  ]
]
```

#### 2. Markdown 表格提取

使用 `markdown` 库解析表格，或使用正则表达式：

```python
import re

def extract_tables_from_markdown(markdown_text: str) -> List[str]:
    """从 Markdown 提取表格 HTML"""
    # Markdown 表格格式：
    # | 列1 | 列2 |
    # |-----|-----|
    # | 值1 | 值2 |
    
    tables = []
    lines = markdown_text.split('\n')
    current_table = []
    in_table = False
    
    for line in lines:
        if '|' in line and not in_table:
            in_table = True
            current_table = [line]
        elif '|' in line and in_table:
            current_table.append(line)
        elif in_table:
            # 表格结束，转换为 HTML
            if current_table:
                html = markdown_table_to_html(current_table)
                tables.append(html)
            in_table = False
            current_table = []
    
    # 处理最后一个表格
    if current_table:
        html = markdown_table_to_html(current_table)
        tables.append(html)
    
    return tables
```

#### 3. 调用 generate_document_html.py

```python
# 方案 A：直接调用函数（需要重构脚本）
from scripts.generate_document_html import (
    generate_document_html,
    generate_index_json
)

# 生成 HTML
html_content = generate_document_html(
    doc_name=material.name,
    pages_data=pages_data,
    images_base_path="images"
)

# 生成索引
index_data = generate_index_json(
    doc_name=material.name,
    file_name=material.name,
    pages_data=pages_data
)

# 方案 B：子进程调用（简单但不优雅）
import subprocess
subprocess.run([
    "python", 
    "scripts/generate_document_html.py",
    "--input", str(content_list_path),
    "--output", str(output_dir)
])
```

#### 4. 存储结构

```
data/
  documents/
    {material_id}/
      vlm/
        {material_name}_content_list_v2.json
        images/
          material_{id}_page_1.png
          material_{id}_page_2.png
      document.html
      index.json
```

---

## 实现步骤

### Phase 1: 准备工作（10分钟）

1. **创建工具函数**
   - 文件：`backend/app/utils/markdown_utils.py`
   - 函数：`extract_tables_from_markdown()`, `markdown_table_to_html()`

2. **创建文档输出目录**
   - 路径：`data/documents/{material_id}/`
   - 确保目录权限正确

### Phase 2: 数据转换（20分钟）

1. **修改 `document_processor.py`**
   - 在 `process_document()` 方法中添加转换逻辑
   - 构建 `pages_data` 结构
   - 保存 `content_list_v2.json`

2. **测试转换逻辑**
   - 单元测试：markdown → content_list_v2.json
   - 集成测试：上传 PDF → 验证 JSON 格式

### Phase 3: HTML 生成（15分钟）

1. **重构 `generate_document_html.py`**
   - 将 `generate_document_html()` 和 `generate_index_json()` 提取为可导入函数
   - 保持命令行入口兼容

2. **在 `document_processor.py` 中调用**
   - 导入生成函数
   - 传入 `pages_data`
   - 保存 HTML 和索引

### Phase 4: 测试验证（15分钟）

1. **端到端测试**
   - 上传 PDF
   - 验证 OCR 完成
   - 验证 `content_list_v2.json` 生成
   - 验证 `document.html` 生成
   - 验证 `index.json` 生成

2. **HierarchicalContext 集成测试**
   - 加载新文档的 HTML 和索引
   - 验证表格和语义检索正常

---

## 关键代码位置

### 需要修改的文件

1. **`backend/app/services/document_processor.py`**
   - 方法：`process_document()`
   - 添加：数据转换 + HTML 生成调用

2. **`scripts/generate_document_html.py`**
   - 重构：提取可导入函数
   - 保持：命令行入口

3. **`backend/app/utils/markdown_utils.py`**（新建）
   - 功能：Markdown 表格提取和转换

### 需要创建的目录

```
data/documents/{material_id}/
  vlm/
    images/
```

---

## 验收标准

### 功能验收

- [ ] 上传 PDF 后自动生成 `content_list_v2.json`
- [ ] 上传 PDF 后自动生成 `document.html`
- [ ] 上传 PDF 后自动生成 `index.json`
- [ ] HTML 包含正确的表格和图片
- [ ] 索引包含正确的表格 ID、工序、材料信息

### 性能验收

- [ ] 不影响现有 OCR 性能（转换时间 < 1秒/页）
- [ ] 不阻塞上传响应（可考虑后台任务）

### 兼容性验收

- [ ] 历史数据（exports_vlm_full）仍然可用
- [ ] generate_document_html.py 命令行仍然可用
- [ ] HierarchicalContext 可以同时加载新旧数据

---

## 风险与缓解

### 风险 1：Markdown 表格提取不准确

**缓解**：
- 使用成熟的 markdown 解析库（markdown, markdown2）
- 添加表格提取测试用例
- 保留原始 markdown 作为备份

### 风险 2：性能影响

**缓解**：
- HTML 生成不阻塞 OCR
- 使用后台任务（可选）
- 缓存生成的 HTML

### 风险 3：数据格式兼容性

**缓解**：
- 严格遵循 content_list_v2.json 格式
- 添加数据验证（JSON Schema）
- 单元测试覆盖格式转换

---

## 后续优化

1. **后台任务**：将 HTML 生成移到 Celery 任务
2. **增量更新**：只处理新增页面
3. **错误恢复**：HTML 生成失败时的重试机制
4. **进度通知**：前端显示 HTML 生成进度

---

## 项目信息

- **项目**：工艺文件知识库（localknowledgebase-word）
- **优先级**：P1（阻塞核心功能）
- **预估工时**：1 小时
- **负责人**：Coder Agent
- **PRP 创建时间**：2026-03-22 17:55
