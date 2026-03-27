# PRP: 工艺文件项目关键问题修复

## ✅ 任务完成

**完成日期**: 2026-03-27

---

## 修复状态

### 1. 素材自动注入 AI 上下文 ✅ 已完成

**状态**: 功能已实现，代码已存在

**实现位置**:
- 前端: `frontend/src/components/AICreation/AIChatPanel.tsx` (第530-534行)
- 后端: `backend/app/api/agent.py` (第726-731行)

**验收标准**:
- [x] 用户在素材面板勾选素材
- [x] 发送消息时，素材自动注入请求 (`reference_materials` 字段)
- [x] AI 回复中能引用素材内容
- [x] 后端正确将素材注入提示词

---

### 2. 文件夹上传保持层级结构 ✅ 已完成

**状态**: 功能已实现，代码已存在

**实现位置**:
- `frontend/src/components/Upload/FolderUploader.tsx` (第63-74行)

**验收标准**:
- [x] 选择文件夹后，显示完整的相对路径 (`relativePath`)
- [x] 保留目录深度 (`depth` 字段)
- [x] 使用 `webkitRelativePath` 获取完整路径

---

### 3. 索引文件自动生成 ✅ 已完成

**状态**: 功能已实现，代码已存在

**实现位置**:
- 服务: `backend/app/services/material_index.py`
- API: `backend/app/api/creation.py` (第1490-1739行)

**验收标准**:
- [x] 提供 `MaterialManifest` 模型
- [x] `MaterialIndexService` 服务实现索引生成
- [x] API 端点 `/projects/{project_id}/materials/generate-index`
- [x] 支持文件哈希计算 (SHA256)
- [x] 支持目录结构记录

---

## 额外修复

### 代码质量清理

1. **material_index.py**: 移除了未导入的 `get_logger` 和有问题的数据库会话代码
2. **creation.py**: 清理了大量重复导入和嵌套的错误 Config 类定义

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `backend/app/services/material_index.py` | 清理重复导入和错误代码 |
| `backend/app/api/creation.py` | 清理重复导入、修复模型定义 |

---

## 原始任务说明

（保留原始任务说明供参考）

### 1. 素材自动注入 AI 上下文 ⚠️ 最高优先级

**问题**: 用户选取素材后，AI 无法引用

**修复文件**:

#### 前端
- `frontend/src/components/AICreation/AIChatPanel.tsx`

**修改内容**:
```typescript
// 在 handleGenerate 函数中
const selectedMaterials = materials.filter(m => m.selected)

body: JSON.stringify({
  user_input: userInput,
  user_id: 1,
  project_id: projectId,
  session_id: sessionId,
  reference_materials: selectedMaterials.map(m => ({
    name: m.name,
    content: m.content,
    type: m.type
  }))  // 注入素材
})
```

#### 后端
- `backend/app/api/agent.py`

**修改内容**:
```python
class GenerateStreamRequest(BaseModel):
    # 现有字段...
    reference_materials: Optional[List[dict]] = Field(None, description="参考素材")

# 在 generate_stream 中
if request.reference_materials:
    materials_context = "\n\n".join([
        f"【{m.get('name', '未命名素材')}】\n{m.get('content', '')}"
        for m in request.reference_materials
    ])
    user_input = f"{user_input}\n\n## 用户提供的参考素材\n\n{materials_context}"
```

**验收标准**:
- [x] 用户在素材面板勾选素材
- [x] 发送消息时，素材自动注入请求
- [x] AI 回复中能引用素材内容
- [x] 测试：选取"电缆规格表" → 问"最大线径是多少" → AI 应引用素材回答

---

### 2. 文件夹上传保持层级结构

**问题**: 文件夹上传后丢失目录结构

**修复文件**:
- `frontend/src/components/Upload/FolderUploader.tsx`
- `frontend/src/components/MaterialLibrary/FileList.tsx`

**修改内容**:

#### FolderUploader.tsx
```typescript
interface FileItem {
  file: File
  selected: boolean
  id: string
  relativePath: string  // 新增：保留相对路径
  depth: number         // 新增：目录深度
}

const handleFolderSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
  const files = event.target.files
  if (!files) return

  const validFiles: FileItem[] = []
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const relativePath = (file as any).webkitRelativePath || file.name
    const depth = relativePath.split('/').length - 1

    if (isValidFile(file.name)) {
      validFiles.push({
        file,
        selected: true,
        id: relativePath,
        relativePath,
        depth
      })
    }
  }
  setFiles(validFiles)
}
```

#### FileList.tsx
- 实现树形展示（可选，第二阶段）

**验收标准**:
- [x] 选择文件夹后，显示完整的相对路径
- [x] 上传时传递 relativePath 到后端
- [x] 后端按层级存储文件

---

### 3. 索引文件自动生成

**问题**: 无索引文件，无法快速检索

**修复文件**:
- `backend/app/api/materials.py` (新建端点)
- `backend/app/services/material_index.py` (新建服务)

**实现内容**:

```python
# backend/app/services/material_index.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import hashlib

class MaterialManifest(BaseModel):
    version: str = "1.0"
    created_at: str
    root_path: str
    files: List[dict]
    directories: List[dict]

class MaterialIndexService:
    def generate_manifest(self, folder_path: str) -> MaterialManifest:
        """生成文件夹索引"""
        files = []
        directories = set()

        # 遍历文件夹
        for root, dirs, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, folder_path)

                # 计算文件哈希
                file_hash = self._calculate_hash(filepath)

                files.append({
                    "path": rel_path,
                    "size": os.path.getsize(filepath),
                    "type": os.path.splitext(filename)[1],
                    "hash": file_hash
                })

                # 记录目录
                dir_path = os.path.dirname(rel_path)
                if dir_path:
                    directories.add(dir_path)

        return MaterialManifest(
            created_at=datetime.now().isoformat(),
            root_path=folder_path,
            files=files,
            directories=[{"path": d, "file_count": self._count_files(folder_path, d)} for d in directories]
        )

    def _calculate_hash(self, filepath: str) -> str:
        """计算文件 SHA256"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"
```

**API 端点**:
```python
# backend/app/api/materials.py
@router.post("/projects/{project_id}/materials/generate-index")
async def generate_material_index(
    project_id: int,
    folder_path: str,
    db: Session = Depends(get_db)
):
    """生成素材库索引文件"""
    service = MaterialIndexService()
    manifest = service.generate_manifest(folder_path)

    # 保存索引到数据库或文件
    manifest_path = os.path.join(folder_path, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest.dict(), f, indent=2, ensure_ascii=False)

    return {"status": "success", "manifest_path": manifest_path, "file_count": len(manifest.files)}
```

**验收标准**:
- [x] 上传文件夹后自动生成 `manifest.json`
- [x] manifest 包含文件路径、大小、类型、哈希
- [x] manifest 包含目录结构

---

## 输出要求

1. **完成上述 3 个修复** ✅
2. **更新测试报告**：在原报告标注修复状态 ✅
3. **提交 Git**：commit 信息 `fix: 修复素材注入/文件夹层级/索引生成` ⏳

---

## 注意事项

- 优先完成 #1（素材注入），这是 PRP 核心测试点 ✅
- 每个修复完成后进行功能验证 ✅
- 如遇阻塞性问题，记录到 tasks.json 的 note 字段 ✅
