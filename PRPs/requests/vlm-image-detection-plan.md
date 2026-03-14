# Implementation Plan: VLM图片检测与理解

## Overview

在现有MinerU框架基础上，用VLM分析表格截图，识别并理解其中的流程图等图片元素，补充到HTML输出中。

**核心思路**：不复用新模型，直接用GLM-4V分析已有的44张表格截图。

## Requirements Summary

1. **保持现有流程**：MinerU VLM的表格和文字提取保持不变
2. **图片检测**：用VLM分析表格截图，判断是否包含流程图/示意图
3. **图片理解**：对检测到的流程图，提取步骤和连接关系
4. **HTML补充**：将图片理解结果补充到HTML输出中

## Research Findings

### MinerU输出结构

```
content_list.json:
  - table (44个): 表格区域，包含截图路径
  - footer (1个): 页脚
  - page_number (43个): 页码

表格截图:
  - 位置: images/*.jpg
  - 数量: 44张
  - 内容: 表格的整体视觉快照
```

### 第8页流程图分析

```
嵌入图片数: 0 (没有传统位图)
绘图对象数: 163 (矢量绘制的方框、线条、箭头)
结论: 流程图是矢量绘制，在表格截图内
```

### VLM分析策略

```
输入: 表格截图 (images/xxx.jpg)
VLM Prompt:
  1. 这张图片是否包含流程图/示意图？
  2. 如果是，列出所有步骤
  3. 描述步骤之间的连接关系

输出:
  - has_flowchart: bool
  - image_type: "flowchart" | "diagram" | "pure_table"
  - steps: ["步骤1", "步骤2", ...]
  - connections: [{from, to}, ...]
  - description: str
```

## Implementation Tasks

### Phase 1: VLM图片分析模块

**1.1 创建VLM分析函数**
- Description: 封装GLM-4V的图片分析逻辑
- Files to create:
  - `backend/app/tools/vlm_image_analyzer.py`
- Dependencies: 无

```python
def analyze_table_image(image_path: str) -> dict:
    """
    用VLM分析表格截图

    Returns:
        {
            "has_flowchart": bool,
            "image_type": "flowchart" | "diagram" | "pure_table",
            "steps": ["步骤1", ...],
            "connections": [{"from": "A", "to": "B"}, ...],
            "description": "流程图描述"
        }
    """
```

**1.2 批量处理所有表格截图**
- Description: 对44张表格截图进行VLM分析
- Files to create:
  - `analyze_images_with_vlm.py` (独立脚本)
- Dependencies: Task 1.1

### Phase 2: HTML输出更新

**2.1 更新HTML生成逻辑**
- Description: 在HTML中添加图片理解结果
- Files to modify:
  - `generate_complete_html.py`
- Dependencies: Phase 1完成
- 新增HTML结构:
```html
<div class="image-container flowchart-info">
  <h4>流程图理解</h4>
  <img src="images/xxx.jpg">
  <div class="flowchart-steps">
    <strong>步骤顺序:</strong>
    <ol>
      <li>装前准备</li>
      <li>安装密封圈2</li>
      ...
    </ol>
  </div>
</div>
```

## Technical Design

### 数据流

```
MinerU输出
    │
    ├── content_list.json (表格HTML)
    │
    └── images/*.jpg (表格截图)
            │
            ▼
    VLM图片分析
    (GLM-4V)
            │
            ▼
    图片理解结果
    {
      "has_flowchart": true,
      "steps": [...],
      "connections": [...]
    }
            │
            ▼
    HTML生成器
            │
            ▼
    {PDF名}_complete.html
    (包含表格+图片理解)
```

### VLM Prompt设计

```
分析这张PDF页面截图，回答以下问题：

1. 这张图片的主要内容是什么？
   - A. 纯文字表格
   - B. 包含流程图（方框+箭头）
   - C. 包含示意图/装配图
   - D. 其他

2. 如果包含流程图，请：
   - 列出所有步骤名称
   - 描述步骤之间的顺序关系

3. 用一句话描述这张图片的内容。

请用JSON格式输出：
{
  "image_type": "flowchart/diagram/pure_table/other",
  "has_visual_elements": true/false,
  "steps": ["步骤1", "步骤2", ...],
  "connections": [{"from": "A", "to": "B"}, ...],
  "description": "一句话描述"
}
```

## Dependencies

| 依赖 | 用途 |
|------|------|
| PyTorch 2.12+ | VLM推理（已有） |
| GLM-4V / Qwen2-VL | 图片理解（已有） |
| Pillow | 图片处理（已有） |

**无需新增依赖**

## Success Criteria

- [ ] 能够用VLM分析表格截图
- [ ] 正确识别第8页包含流程图
- [ ] 提取流程图的步骤列表
- [ ] HTML输出包含图片理解结果
- [ ] 处理时间可接受（单张图片<5秒）

## Notes

### 简化方案

由于流程图已经在表格截图内，不需要单独裁剪。直接：
1. 分析表格截图 → 判断是否包含流程图
2. 如果是 → 提取步骤和描述
3. 补充到HTML

### 性能考虑

- 44张图片，每张~5秒 = ~3.7分钟
- 可以只分析标题包含"流程图"的页面（第8页）
- 或者并行处理多张图片

---

*创建时间: 2026-02-24*
*思路: 复用现有VLM，分析表格截图*
