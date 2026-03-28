# 素材库重构任务清单

> 2026-03-28 | 需要逐步完成并测试

---

## 任务列表

### Task 1：数据库字段清理（基础）

**目标**：删除冗余字段，只保留元数据

**修改文件**：
- `backend/app/models/database.py`

**具体操作**：
1. 修改 `Material` 模型：
   - 保留：id, name, material_type, created_at, updated_at
   - 删除：content, search_result_id

2. 修改 `MaterialPage` 模型：
   - 保留：id, material_id, page_number, image_path, created_at
   - 删除：text_content, figures

3. 创建数据库迁移脚本：
   - 备份现有数据到文件系统
   - 删除字段

**测试项**：
```python
# 测试1：模型定义正确
from app.models.database import Material, MaterialPage
assert hasattr(Material, 'id')
assert hasattr(Material, 'name')
assert not hasattr(Material, 'content')  # 已删除

# 测试2：数据库迁移成功
# 启动后端，检查表结构
```

**验证命令**：
```bash
cd backend
python -c "from app.models.database import Material; print([c.name for c in Material.__table__.columns])"
# 预期输出: ['id', 'name', 'material_type', 'created_at', 'updated_at']
```

---

### Task 2：重组文件结构

**目标**：统一素材存储路径

**当前结构**：
```
backend/data/
├── uploads/1/material_1_xxx.pdf
├── documents/1/vlm/images/*.png
└── _deprecated/ (已清理)
```

**目标结构**：
```
backend/data/
├── materials/
│   ├── index.json
│   └── 1_全单电缆装配规程/
│       ├── manifest.json
│       ├── original.pdf
│       ├── full.html
│       └── summary.json
└── pages/ (空目录，不存储)
```

**具体操作**：
1. 创建 `backend/data/materials/` 目录
2. 迁移现有素材：
   - 移动 PDF：`uploads/1/` → `materials/1_xxx/original.pdf`
   - 生成 HTML：从现有 JSON 转换
   - 生成索引：创建 `summary.json`

**测试项**：
```python
# 测试1：目录结构正确
import os
assert os.path.exists("backend/data/materials/1_全单电缆装配规程")
assert os.path.exists("backend/data/materials/1_全单电缆装配规程/manifest.json")
assert os.path.exists("backend/data/materials/1_全单电缆装配规程/full.html")
assert os.path.exists("backend/data/materials/1_全单电缆装配规程/summary.json")

# 测试2：索引文件格式正确
import json
with open("backend/data/materials/1_全单电缆装配规程/summary.json") as f:
    summary = json.load(f)
    assert "pages" in summary
    assert "keyword_index" in summary
    assert len(summary["pages"]) == 44
```

---

### Task 3：生成 summary.json

**目标**：为每个素材生成页级索引

**输入**：
- 现有 OCR 数据（`documents/1/vlm/*.json`）
- 页面图片（`documents/1/vlm/images/*.png`）

**输出**：
```json
{
  "version": "1.0",
  "total_pages": 44,
  "total_tokens_estimate": 15000,
  "toc": [...],
  "pages": [
    {
      "page": 1,
      "type": "text",
      "summary": "封面 - 全单电缆装配规程",
      "keywords": ["电缆", "装配", "规程"],
      "tokens_estimate": 50
    },
    // ...
  ],
  "keyword_index": {
    "电缆": [1, 5, 12, 15, 20],
    "装配": [1, 12, 13, 14]
  }
}
```

**实现脚本**：
- 创建 `backend/scripts/generate_summary.py`
- 读取现有 OCR 数据
- 生成摘要和关键词

**测试项**：
```python
# 测试1：索引生成正确
summary = generate_summary(material_id=1)
assert summary["total_pages"] == 44
assert len(summary["pages"]) == 44
assert len(summary["keyword_index"]) > 0

# 测试2：关键词索引有效
pages_with_keyword = summary["keyword_index"].get("电缆", [])
assert len(pages_with_keyword) > 0
```

---

### Task 4：修改 API 路由 ✅ 已完成

**目标**：API 从文件系统读取，不依赖数据库内容

**修改文件**：
- `backend/app/api/materials.py` (新建)
- `backend/main.py` (注册路由)

**已实现接口**：

```python
# 1. 获取素材列表
@router.get("/materials")
async def list_materials():
    # 从 data/materials/index.json 读取

# 2. 获取素材索引
@router.get("/materials/{material_id}/summary")
async def get_material_summary(material_id: int):
    # 从 data/materials/{material_id}_*/summary.json 读取

# 3. 获取具体页面内容
@router.get("/materials/{material_id}/pages/{page_num}")
async def get_page_content(material_id: int, page_num: int):
    # 返回页面信息 + 图片路径

# 4. 获取素材信息
@router.get("/materials/{material_id}")
async def get_material_info(material_id: int):
    # 从 manifest.json + summary.json 读取
```

**测试结果**：
```bash
# 测试1：获取列表 ✅
curl http://localhost:8000/api/materials
# 返回: {"materials":[{"id":1,"name":"全单电缆装配规程","path":"1_全单电缆装配规程","page_count":44}]}

# 测试2：获取索引 ✅
curl http://localhost:8000/api/materials/1/summary
# 返回: total_pages: 44, keyword_index: 4 keywords

# 测试3：获取页面 ✅
curl http://localhost:8000/api/materials/1/pages/5
# 返回: {"material_id":1,"page_number":5,"title":"第5页",...}
```

---

### Task 5：上下文注入服务

**目标**：根据关键词搜索并注入页面内容

**修改文件**：
- `backend/app/services/context_manager.py`

**具体操作**：

```python
class ContextManager:
    def search_and_inject(self, query: str, material_ids: List[int]) -> str:
        """
        搜索关键词并注入相关页面内容

        返回格式：
        <context>
          <source material="全单电缆装配规程" pages="12-13">
            第12页内容：...
            第13页内容：...
          </source>
        </context>
        """
        # 1. 从内存索引搜索关键词
        relevant_pages = self._search_keywords(query, material_ids)

        # 2. 读取页面内容
        context_parts = []
        for material_id, pages in relevant_pages.items():
            for page_num in pages:
                content = self._read_page_content(material_id, page_num)
                context_parts.append(content)

        # 3. 格式化返回
        return self._format_context(context_parts)
```

**测试项**：
```python
# 测试1：搜索关键词
cm = ContextManager()
pages = cm._search_keywords("电缆装配流程", [1])
assert 12 in pages[1] or 13 in pages[1]

# 测试2：注入上下文
context = cm.search_and_inject("电缆装配流程", [1])
assert "<context>" in context
assert "装配" in context
```

---

## 执行顺序

```
Task 1 (数据库) → Task 2 (文件结构) → Task 3 (索引生成)
                                          ↓
Task 5 (上下文注入) ← Task 4 (API修改)
```

---

## 验证清单

每完成一个任务，必须通过以下验证：

- [ ] **代码检查**：语法正确，无错误
- [ ] **单元测试**：测试项全部通过
- [ ] **集成测试**：与现有系统兼容
- [ ] **日志检查**：无异常日志

---

## 监控要求

Coder 执行时，Main Agent 需要监控：

1. **OpenClaw 日志**：`C:\Users\alerl\.openclaw\logs\`
2. **Claude Code 日志**：Session transcript
3. **后端日志**：`backend/data/logs/`

发现异常立即反馈。
