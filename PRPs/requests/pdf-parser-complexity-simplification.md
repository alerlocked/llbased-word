# PDF解析流程简化计划 - 双复杂度模式

## 需求概述

简化现有PDF解析流程，从多级复杂度选择简化为两个明确的复杂度模式：
1. **无表格模式** → 使用普通方法 (PyMuPDF)
2. **有表格模式** → 使用 mineru-vlm 高精度解析

## 现有架构分析

### 当前流程

```
PDF文件
    ↓
ParserSelector.analyze_document()
    ├── 检测表格数量
    ├── 检测无边框表格
    ├── 检测合并单元格
    ├── 检测多页表格
    ├── 计算中文比例
    ↓
计算复杂度分数 (0-1)
    ↓
选择解析器:
    - score > 0.8 → MINERU (pipeline)
    - score > 0.7 → PDFPLUMBER
    - score < 0.3 → PYMUPDF
    - 其他 → HYBRID
    ↓
PDFParser.parse()
    ↓
输出结果
```

### 涉及文件

| 文件 | 作用 | 修改程度 |
|------|------|----------|
| `backend/app/tools/pdf_parser.py` | 主解析器 | 中 |
| `backend/app/tools/parser_selector.py` | 解析器选择 | 高 |
| `backend/app/tools/table_extractors/mineru_extractor.py` | MinerU提取器 | 低 |
| `backend/app/models/table_models.py` | 数据模型 | 低 |
| `backend/app/shared/config.py` | 配置文件 | 低 |

## 目标架构

### 新流程

```
PDF文件
    ↓
ParserSelector.quick_detect_tables()
    ├── 使用PyMuPDF快速检测是否有表格
    └── 返回: has_tables (bool)
    ↓
┌─────────────────────────────────────────┐
│           复杂度判断                      │
├─────────────────────────────────────────┤
│  has_tables == False                    │
│      ↓                                  │
│  简单模式: PyMuPDF                       │
│  - 文本提取                              │
│  - 图像提取 (可选)                        │
│  - 无表格处理                            │
├─────────────────────────────────────────┤
│  has_tables == True                     │
│      ↓                                  │
│  复杂模式: MinerU-VLM                    │
│  - 表格识别 (TableFormer)                │
│  - 合并单元格处理                         │
│  - 跨页表格合并                          │
│  - 高精度结构识别                         │
└─────────────────────────────────────────┘
    ↓
统一输出格式
```

## 实现任务

### Task 1: 修改 ParserSelector

**文件**: `backend/app/tools/parser_selector.py`

**改动**:
1. 新增 `quick_detect_tables()` 方法 - 快速检测是否有表格
2. 简化 `select_parser()` 逻辑 - 只返回 SIMPLE 或 COMPLEX
3. 移除复杂度分数计算 - 改为布尔判断
4. 更新 `ParserType` 枚举

```python
class ParserType(Enum):
    """解析器类型 - 简化为两种"""
    SIMPLE = "simple"      # 简单模式: PyMuPDF (无表格)
    COMPLEX = "complex"    # 复杂模式: MinerU-VLM (有表格)
```

### Task 2: 修改 PDFParser

**文件**: `backend/app/tools/pdf_parser.py`

**改动**:
1. 简化 `parse()` 方法入口
2. 添加 `_parse_simple()` 方法 - PyMuPDF快速解析
3. 修改 `_extract_tables()` 调用 MinerU VLM 后端
4. 统一输出格式

### Task 3: 更新 MinerU 配置

**文件**: `backend/app/shared/config.py`

**改动**:
1. 添加 `MINERU_VLM_CONFIG` 配置
2. 默认使用 `vlm-auto-engine` 后端
3. 配置表格专用参数

```python
MINERU_VLM_CONFIG = {
    "enabled": True,
    "backend": "vlm-auto-engine",  # VLM高精度模式
    "table_enable": True,
    "lang": "ch",
    "timeout_seconds": 300,
}
```

### Task 4: 更新数据模型

**文件**: `backend/app/models/table_models.py`

**改动**:
1. 简化 `ParserType` 枚举
2. 更新 `ParserSelectionResult` 数据结构

### Task 5: 更新测试

**文件**: `backend/tests/tools/test_parser_selector.py`

**改动**:
1. 添加无表格PDF测试用例
2. 添加有表格PDF测试用例
3. 验证解析器选择逻辑

## API 变更

### 请求参数

```python
# 现有
{
    "extract_tables": true,
    "extract_text": true,
    "preferred_parser": "auto"  # 移除
}

# 新版
{
    "extract_tables": true,
    "extract_text": true,
    "force_mode": null  # 可选: "simple" | "complex" | null(自动)
}
```

### 响应格式

```python
{
    "pages": [...],
    "tables": [...],  # 仅复杂模式
    "document_info": {...},
    "metadata": {
        "parser_mode": "simple" | "complex",
        "parser_used": "pymupdf" | "mineru-vlm",
        "has_tables": true | false,
        "table_count": 0
    }
}
```

## 验证标准

### 功能验证

- [ ] 无表格PDF使用简单模式 (PyMuPDF)
- [ ] 有表格PDF使用复杂模式 (MinerU-VLM)
- [ ] 强制模式参数生效
- [ ] 输出格式统一

### 性能验证

- [ ] 简单模式解析速度 < 1s/页
- [ ] 复杂模式解析速度可接受 (< 10s/页)
- [ ] 内存使用合理

### 兼容性验证

- [ ] 现有API调用不受影响
- [ ] 前端展示正常

## 文件修改清单

```
backend/
├── app/
│   ├── tools/
│   │   ├── pdf_parser.py           # 修改
│   │   ├── parser_selector.py      # 重构
│   │   └── table_extractors/
│   │       └── mineru_extractor.py # 微调
│   ├── models/
│   │   └── table_models.py         # 修改
│   └── shared/
│       └── config.py               # 添加配置
└── tests/
    └── tools/
        └── test_parser_selector.py # 更新测试
```

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| MinerU-VLM需要GPU | 中 | 添加CPU回退模式 |
| 解析速度变慢 | 低 | 仅在有表格时使用复杂模式 |
| 输出格式变化 | 低 | 保持向后兼容 |

## 执行顺序

1. **Phase 1**: 数据模型更新 (ParserType)
2. **Phase 2**: ParserSelector 重构
3. **Phase 3**: PDFParser 修改
4. **Phase 4**: 配置更新
5. **Phase 5**: 测试验证

---

*创建时间: 2026-03-04*
*预计工时: 2-3小时*
