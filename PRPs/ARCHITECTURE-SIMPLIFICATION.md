# 架构优化方案：简化素材管理

**提出时间**: 2026-03-07 13:36  
**优先级**: 🔴 高  
**目标**: 简化架构，去除向量数据库，直接管理HTML素材

---

## 📊 **当前架构问题**

### 问题1：功能重叠
```
素材库（Materials）  ←→  PDF工艺文档（Documents）
     ↓                        ↓
   都可以上传文档           都可以解析表格
     ↓                        ↓
   功能重复，用户困惑
```

### 问题2：向量数据库复杂
- 需要维护 ChromaDB
- 需要 Embedding API
- 检索结果不确定
- 占用资源
- 对于结构化文档不必要

### 问题3：素材管理混乱
- 项目素材 vs 系统素材
- 没有明确的层级关系
- 不支持文件夹批量导入

---

## ✅ **新架构设计**

### 核心思路
```
系统素材库（全局）
    ├─ 文件夹1（工艺规程）
    │   ├─ 文档1.html
    │   ├─ 文档2.html
    │   └─ ...
    ├─ 文件夹2（操作说明）
    │   └─ ...
    └─ ...

    ↓ 可添加到项目

项目素材库
    ├─ 引用系统素材（软链接）
    ├─ 项目专属素材
    └─ ...

    ↓ AI按需加载

AI 上下文
    └─ 直接读取HTML内容
```

---

## 🎯 **实施方案**

### 方案1：完全重新设计（推荐）

#### 1. **数据库设计**

```sql
-- 系统素材库
CREATE TABLE system_materials (
    id SERIAL PRIMARY KEY,
    folder_name VARCHAR(255),        -- 所属文件夹
    file_name VARCHAR(255),          -- 文件名
    file_type VARCHAR(50),           -- pdf/docx/html
    html_path VARCHAR(500),          -- HTML文件路径
    source_path VARCHAR(500),        -- 原始文件路径
    file_order INT,                  -- 在文件夹中的顺序
    metadata JSONB,                  -- 元数据
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 项目素材关联表
CREATE TABLE project_materials (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES creation_projects(id),
    system_material_id INT REFERENCES system_materials(id),
    is_reference BOOLEAN DEFAULT true,  -- 是否为引用（软链接）
    added_at TIMESTAMP,
    added_by INT
);

-- 如果是项目专属素材
CREATE TABLE project_private_materials (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES creation_projects(id),
    file_name VARCHAR(255),
    html_path VARCHAR(500),
    metadata JSONB,
    created_at TIMESTAMP
);
```

#### 2. **文件夹上传流程**

```
用户上传文件夹
    ↓
后端遍历文件夹
    ↓
按顺序解析每个文件（PDF/Word/图片）
    ↓
转换为HTML
    ├─ 保存到 data/materials/{folder_name}/{file_name}.html
    └─ 记录到 system_materials 表
    ↓
返回上传结果
```

#### 3. **AI 使用流程**

```
用户提问
    ↓
前端传递：项目ID + 问题
    ↓
后端：
    1. 查询项目关联的素材（project_materials）
    2. 读取 HTML 文件内容
    3. 拼接为上下文（限制长度，避免堵塞）
    4. 调用 LLM 生成回答
    ↓
流式返回结果
```

---

### 方案2：渐进式改造（快速）

#### 阶段1：先简化存储（1小时）
- 保留现有 API
- 去掉向量数据库
- 直接保存为HTML
- AI直接读取HTML

#### 阶段2：添加文件夹支持（2小时）
- 支持文件夹上传
- 批量解析
- 按顺序保存

#### 阶段3：优化素材管理（2小时）
- 系统素材库
- 项目素材关联
- 引用机制

---

## 🔧 **技术实现**

### 1. **文件夹上传**

```python
# backend/app/api/materials.py

@router.post("/upload-folder")
async def upload_folder(
    files: List[UploadFile] = File(...),
    folder_name: str = Form(...)
):
    """上传文件夹"""
    logger.info(f"📁 上传文件夹: {folder_name}, 文件数: {len(files)}")
    
    # 按文件名排序
    sorted_files = sorted(files, key=lambda f: f.filename)
    
    created_materials = []
    
    for idx, file in enumerate(sorted_files):
        # 解析文件
        content = await parse_file(file)
        
        # 转换为HTML
        html_content = convert_to_html(content)
        
        # 保存HTML文件
        html_path = f"data/materials/{folder_name}/{file.filename}.html"
        save_html_file(html_path, html_content)
        
        # 记录到数据库
        material = SystemMaterial(
            folder_name=folder_name,
            file_name=file.filename,
            html_path=html_path,
            file_order=idx
        )
        db.add(material)
        created_materials.append(material)
    
    db.commit()
    
    return {
        "message": f"成功上传 {len(created_materials)} 个文件",
        "materials": created_materials
    }
```

### 2. **按需加载素材**

```python
# backend/app/services/ai_service.py

async def generate_with_materials(
    user_input: str,
    project_id: int,
    max_context_length: int = 10000  # 限制上下文长度
):
    """基于项目素材生成内容"""
    
    # 1. 查询项目素材
    materials = db.query(ProjectMaterial).filter(
        ProjectMaterial.project_id == project_id
    ).all()
    
    # 2. 读取HTML内容（按需，不堵塞）
    context_parts = []
    current_length = 0
    
    for material in materials:
        # 读取HTML文件
        html_content = read_html_file(material.html_path)
        
        # 提取纯文本（去除HTML标签）
        text_content = extract_text_from_html(html_content)
        
        # 检查长度限制
        if current_length + len(text_content) > max_context_length:
            # 截断或跳过
            remaining = max_context_length - current_length
            if remaining > 100:  # 至少保留100字符
                text_content = text_content[:remaining]
                context_parts.append(text_content)
            break
        
        context_parts.append(text_content)
        current_length += len(text_content)
    
    # 3. 拼接上下文
    context = "\n\n---\n\n".join(context_parts)
    
    # 4. 调用LLM
    prompt = f"""基于以下参考内容回答用户问题：

【参考内容】
{context}

【用户问题】
{user_input}

【要求】
- 优先使用参考内容中的信息
- 如果参考内容中没有相关信息，请明确说明
- 回答专业、准确
"""
    
    # 5. 流式生成
    async for chunk in llm_service.stream_chat(prompt):
        yield chunk
```

### 3. **系统素材库管理**

```python
# backend/app/api/materials.py

@router.get("/system-materials")
async def list_system_materials(
    folder_name: Optional[str] = None
):
    """列出系统素材库"""
    query = db.query(SystemMaterial)
    
    if folder_name:
        query = query.filter(SystemMaterial.folder_name == folder_name)
    
    materials = query.order_by(SystemMaterial.folder_name, SystemMaterial.file_order).all()
    
    # 按文件夹分组
    grouped = {}
    for m in materials:
        if m.folder_name not in grouped:
            grouped[m.folder_name] = []
        grouped[m.folder_name].append(m)
    
    return grouped


@router.post("/projects/{project_id}/add-materials")
async def add_materials_to_project(
    project_id: int,
    material_ids: List[int]
):
    """将系统素材添加到项目"""
    for material_id in material_ids:
        # 检查是否已添加
        existing = db.query(ProjectMaterial).filter(
            ProjectMaterial.project_id == project_id,
            ProjectMaterial.system_material_id == material_id
        ).first()
        
        if not existing:
            # 创建引用
            project_material = ProjectMaterial(
                project_id=project_id,
                system_material_id=material_id,
                is_reference=True
            )
            db.add(project_material)
    
    db.commit()
    
    return {"message": f"成功添加 {len(material_ids)} 个素材"}
```

---

## 📁 **文件存储结构**

```
data/
└── materials/
    ├── 工艺规程/
    │   ├── 01-总则.html
    │   ├── 02-装配工艺.html
    │   ├── 03-检验标准.html
    │   └── ...
    ├── 操作说明/
    │   ├── 设备操作-01.html
    │   ├── 设备操作-02.html
    │   └── ...
    └── 安全规范/
        ├── 安全规程-01.html
        └── ...
```

---

## ⚡ **性能优化**

### 1. **避免堵塞**
```python
# 使用异步IO读取文件
async def read_html_file_async(path: str) -> str:
    """异步读取HTML文件"""
    async with aiofiles.open(path, 'r', encoding='utf-8') as f:
        return await f.read()

# 并发读取多个文件
async def read_multiple_files(paths: List[str]) -> List[str]:
    """并发读取多个文件"""
    tasks = [read_html_file_async(p) for p in paths]
    return await asyncio.gather(*tasks)
```

### 2. **智能截断**
```python
def smart_truncate(text: str, max_length: int) -> str:
    """智能截断（保留关键信息）"""
    if len(text) <= max_length:
        return text
    
    # 优先保留：
    # 1. 标题
    # 2. 表格数据
    # 3. 关键段落
    
    # 简单实现：截断到句号
    truncated = text[:max_length]
    last_period = truncated.rfind('。')
    if last_period > 0:
        return truncated[:last_period + 1]
    return truncated
```

### 3. **缓存机制**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_material(material_id: int) -> str:
    """缓存素材内容"""
    material = db.query(SystemMaterial).get(material_id)
    return read_html_file(material.html_path)
```

---

## 🎯 **可行性评估**

### ✅ **优点**
1. **架构简单** - 去掉向量数据库，减少复杂度
2. **可控性强** - 直接操作HTML文件，易于调试
3. **不堵塞** - 按需加载，限制长度
4. **支持批量** - 文件夹上传，批量处理
5. **引用机制** - 系统素材可重复使用
6. **易于维护** - 文件系统直观，易于备份

### ⚠️ **注意事项**
1. **文件数量** - 如果文件太多（>1000），需要索引优化
2. **上下文长度** - 需要智能选择最相关的内容
3. **并发控制** - 多人同时访问需要并发控制

### 📊 **性能预估**
```
单个文件读取: <10ms
10个文件并发读取: <100ms
上下文拼接: <50ms
LLM生成: 2-5秒
─────────────────────
总响应时间: <6秒（可接受）
```

---

## 🚀 **实施计划**

### 立即执行（1小时）
1. 创建新的数据库表
2. 实现文件夹上传API
3. 实现素材列表API

### 第二阶段（2小时）
4. 实现项目素材关联
5. 修改AI生成逻辑
6. 前端界面调整

### 第三阶段（2小时）
7. 性能优化
8. 测试验证
9. 文档完善

**总计：5小时完成**

---

## 📋 **迁移计划**

### 数据迁移
```python
# 将现有PDF文档迁移到新结构
async def migrate_existing_documents():
    documents = db.query(Document).all()
    
    for doc in documents:
        # 读取现有HTML
        html_path = f"exports_vlm_full/{doc.id}_complete.html"
        if os.path.exists(html_path):
            # 复制到新位置
            new_path = f"data/materials/导入文档/{doc.name}.html"
            shutil.copy(html_path, new_path)
            
            # 创建记录
            material = SystemMaterial(
                folder_name="导入文档",
                file_name=doc.name,
                html_path=new_path
            )
            db.add(material)
    
    db.commit()
```

---

## ✅ **结论**

**完全可行！** 这个方案：
- ✅ 解决了功能重叠问题
- ✅ 简化了架构
- ✅ 提高了可控性
- ✅ 支持批量导入
- ✅ 不会堵塞

**建议立即实施！**

---

**创建时间**: 2026-03-07 13:36  
**预计完成**: 2026-03-07 18:36  
**负责人**: AI Assistant
