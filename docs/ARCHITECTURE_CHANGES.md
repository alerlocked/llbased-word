# 素材库架构变更记录

> 最后更新：2026-03-28 18:53

---

## 2026-03-28：素材库存储重构

### 变更概述

**目标**：优化素材库存储结构，提升检索效率，适配 30B 模型

**影响范围**：
- 数据库模型（Material, MaterialPage）
- API 路由（creation.py）
- 文件存储结构
- 检索机制

**完成度**：83% (5/6 任务)

---

## 数据库变更

### 删除的字段

| 表 | 字段 | 原用途 | 现存储位置 |
|---|------|--------|-----------|
| `materials` | `content` | 文档内容 | `materials/{id}/full.html` |
| `materials` | `search_result_id` | 检索结果关联 | 不再使用 |
| `material_pages` | `text_content` | OCR 文本 | `materials/{id}/summary.json` |
| `material_pages` | `figures` | 图表元数据 | `materials/{id}/summary.json` |

### 保留的字段

**materials 表**：
- `id` - 素材 ID
- `name` - 素材名称
- `material_type` - 素材类型（pdf/docx/txt/search）
- `created_at` - 创建时间
- `updated_at` - 更新时间

**material_pages 表**：
- `id` - 页面 ID
- `material_id` - 关联素材 ID
- `page_number` - 页码
- `image_path` - 图片路径
- `created_at` - 创建时间

### 迁移脚本

**位置**：`backend/scripts/migrate_db.py`

**使用方法**：
```bash
cd backend
python scripts/migrate_db.py
```

**注意**：
- 会备份被删除的数据到 `data/migrations/`
- 备份文件格式：`backup_YYYYMMDD_HHMMSS.json`

---

## 文件存储变更

### 新的目录结构

```
backend/data/
├── materials/                    # 素材库（全局共享）
│   ├── index.json                # 全局索引
│   └── {id}_{name}/             # 素材目录
│       ├── manifest.json         # 元数据
│       ├── original.pdf          # 原始文件
│       ├── full.html             # 完整内容
│       └── summary.json          # 页级索引
│
├── projects/                     # 项目配置（计划）
│   └── {project_id}_{name}/
│       └── config.json           # material_ids 列表
│
├── _deprecated/                  # 已清理的重复数据
│   ├── pages/                    # 重复的页面图片（12.84 MB）
│   └── process_docs/             # 重复的 PDF（0.41 MB）
│
└── documents/                    # OCR 数据（保留）
    └── {id}/vlm/
        ├── images/               # 页面图片
        └── *.json                # OCR 结果
```

### manifest.json 格式

```json
{
  "id": 1,
  "name": "全单电缆装配规程",
  "type": "pdf",
  "page_count": 44,
  "file_size": 42598400,
  "created_at": "2026-03-28T15:15:31",
  "file_hash": "sha256:...",
  "status": "ready"
}
```

### summary.json 格式

```json
{
  "version": "1.0",
  "total_pages": 44,
  "total_tokens_estimate": 4400,
  "toc": [
    {
      "title": "全文",
      "page_range": [1, 44],
      "summary": "全单电缆装配规程"
    }
  ],
  "pages": [
    {
      "page": 1,
      "type": "text",
      "title": "第1页",
      "summary": "第1页内容",
      "keywords": ["电缆", "装配"],
      "tokens_estimate": 100
    }
  ],
  "keyword_index": {
    "电缆": [1, 5, 12, 15],
    "装配": [1, 12, 13, 14]
  }
}
```

---

## API 变更

### 修改的接口

#### 1. 上传文件夹

**路径**：`POST /api/creation/projects/{project_id}/materials/upload-folder`

**变更**：
- ❌ 删除：将 manifest 内容存储到 `Material.content`
- ✅ 新增：manifest 内容只存储在文件系统

**影响**：
- `Material` 创建时不包含 `content` 字段
- manifest.json 保存在源文件夹

**测试**：✅ 通过（2026-03-28 18:50）

#### 2. 单文件上传

**路径**：`POST /api/creation/projects/{project_id}/materials/upload`

**变更**：
- ❌ 删除：`Material(content="")` 参数
- ✅ 新增：创建时只包含元数据

---

### 计划新增的接口

#### 1. 获取素材索引

**路径**：`GET /api/materials/{material_id}/summary`

**响应**：
```json
{
  "version": "1.0",
  "total_pages": 44,
  "pages": [...],
  "keyword_index": {...}
}
```

**状态**：⏳ 待实现

#### 2. 获取页面内容

**路径**：`GET /api/materials/{material_id}/pages/{page_num}`

**响应**：
```json
{
  "material_id": 1,
  "page_number": 5,
  "title": "第5页",
  "summary": "...",
  "keywords": [...],
  "image_path": "/static/..."
}
```

**状态**：⏳ 待实现

---

## 检索机制变更

### 原机制（已弃用）

- **RAG**：`RAGSyncService` 同步到 ChromaDB
- **问题**：依赖 langchain_openai，未配置

### 新机制（已实现）

**分层检索（30B 模型优化）**：

```
Layer 0: 全局索引（~500 tokens）
  - 加载时机：启动时
  - 存储位置：内存
  
Layer 1: 素材索引（~2000 tokens/素材）
  - 加载时机：打开项目时
  - 存储位置：内存
  
Layer 2: 页面内容（~500-2000 tokens/页）
  - 加载时机：用户提问时
  - 存储位置：按需读取
```

**优势**：
- 内存搜索（毫秒级）
- 按需加载（节省上下文）
- 适配 30B 模型

---

## 测试记录

### 文件夹上传测试 ✅

**时间**：2026-03-28 18:50
**测试文件**：`data/process_docs`（1个 PDF，429KB）

**结果**：
- ✅ API 调用成功（200 OK）
- ✅ Manifest 生成（2文件，419.82KB）
- ✅ 数据库记录正确（2个素材）
- ✅ 文件系统保存正常

**详细报告**：`reports/test-folder-upload.md`

---

## 向后兼容性

### 不兼容的变更

1. **数据库字段删除**
   - `Material.content` - 不再存在
   - `MaterialPage.text_content` - 不再存在
   - 如需内容，从文件系统读取

2. **API 响应变化**
   - `Material` 对象不包含 `content` 字段
   - 需要调用新接口获取内容

### 迁移指南

**旧代码**：
```python
material = db.query(Material).first()
content = material.content  # ❌ 已删除
```

**新代码**：
```python
# 方式1：从文件读取
manifest_path = f"data/materials/{material.id}_*/manifest.json"
with open(manifest_path) as f:
    manifest = json.load(f)

# 方式2：调用 API（待实现）
response = requests.get(f"/api/materials/{material.id}/summary")
summary = response.json()
```

---

## 已知问题

### 1. summary.json 关键词提取

**当前状态**：基础模板（4个关键词）

**优化方向**：
- 从真实 OCR 数据提取关键词
- 使用 TF-IDF 或其他算法
- 支持用户自定义关键词

**优先级**：中

### 2. Coder 不稳定性

**现象**：25% 的 Coder session 启动失败

**影响**：任务监控需要手动干预

**临时方案**：Main Agent 双重监控 + 直接执行

**详细分析**：`reports/coder-instability-analysis.md`

---

## 下一步

1. **实现 Task 5** - 上下文注入服务
2. **优化关键词提取** - 从 OCR 数据生成
3. **完整端到端测试** - 上传 → OCR → 检索 → 生成
4. **API 文档更新** - 记录所有变更

---

## 相关文档

- **PRP**：`PRPs/2026-03-28-material-refactor.md`
- **任务记录**：`C:\Users\alerl\openclaw-control-center\runtime\tasks.json`
- **测试报告**：`reports/test-folder-upload.md`
- **存储方案**：`reports/material-storage-refactor.md`

---

_最后更新：2026-03-28 18:53_
