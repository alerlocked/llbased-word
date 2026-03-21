# PRP: 素材库重构 - 文件系统管理 + 知识库范围选择

## 项目
localknowledgebase-word

## 目标
1. 移除冗余的 PDF 文档功能
2. 重构素材库为文件系统管理
3. 添加知识库范围选择（类似 Get 笔记）

## 当前问题

```yaml
功能重叠:
  PDF 文档:
    - 上传 PDF
    - 查看 PDF 列表
    - 解析 PDF
  
  素材库:
    - 上传文件（包括 PDF）
    - 查看文件列表
    - 管理文件

问题: 两个功能重复，用户体验混乱
```

## 解决方案

### 1. 移除 PDF 文档功能

**删除文件**:
```
frontend/src/pages/PDFDocumentsPage.tsx
frontend/src/components/PDFDocument*
backend/app/api/pdf_documents.py (如果有)
```

**更新路由**:
```typescript
// frontend/src/App.tsx
// 移除 /pdf-documents 路由
```

### 2. 重构素材库

**新的素材库结构**:
```yaml
素材库:
  - 文件夹树形结构
  - 支持创建/删除/重命名文件夹
  - 文件上传到指定文件夹
  - 文件移动/复制
  - 搜索文件

文件夹示例:
  📁 工艺规程/
    ├─ 📁 型号 A/
    │   ├─ 📄 工艺卡片.pdf
    │   └─ 📄 作业指导书.docx
    ├─ 📁 型号 B/
    └─ 📁 通用文件/

知识库范围选择:
  - 选择特定文件夹作为知识库
  - 类似 Get 笔记选择知识范围
  - RAG 检索时只搜索选中的知识库
```

**UI 设计**:
```tsx
<MaterialLibrary>
  <Sidebar>
    <FolderTree>
      <Folder name="工艺规程" selected>
        <Folder name="型号 A" />
        <Folder name="型号 B" />
      </Folder>
      <Folder name="检验标准" />
    </FolderTree>
    
    <KnowledgeScopeSelector>
      <Checkbox>型号 A</Checkbox>
      <Checkbox>型号 B</Checkbox>
      <Checkbox>通用文件</Checkbox>
    </KnowledgeScopeSelector>
  </Sidebar>
  
  <Content>
    <FileList folder={currentFolder} />
    <UploadButton />
  </Content>
</MaterialLibrary>
```

### 3. 知识库范围选择

**功能**:
```yaml
选择知识库:
  - 勾选文件夹
  - RAG 检索时只搜索勾选的文件夹
  - 类似 Get 笔记的知识范围选择

UI:
  <KnowledgeScopeSelector>
    <Header>选择知识库范围</Header>
    <FolderCheckbox>📁 工艺规程/型号 A</FolderCheckbox>
    <FolderCheckbox>📁 工艺规程/型号 B</FolderCheckbox>
    <FolderCheckbox>📁 检验标准</FolderCheckbox>
    <ApplyButton>应用到检索</ApplyButton>
  </KnowledgeScopeSelector>
```

## 任务拆分

### piv_001: 移除 PDF 文档功能
- [ ] 删除 PDFDocumentsPage.tsx
- [ ] 移除路由 /pdf-documents
- [ ] 清理导航菜单
- [ ] 保留 PDF 解析功能（后端）

### piv_002: 重构素材库 UI
- [ ] 添加文件夹树形结构
- [ ] 实现文件夹创建/删除/重命名
- [ ] 文件上传到指定文件夹
- [ ] 文件移动功能

### piv_003: 知识库范围选择
- [ ] 创建 KnowledgeScopeSelector 组件
- [ ] 添加文件夹选择逻辑
- [ ] RAG 检索时过滤知识库
- [ ] 保存用户选择（localStorage）

### piv_004: 后端 API 更新
- [ ] 文件夹 CRUD API
- [ ] 文件移动 API
- [ ] 知识库范围过滤 API

## 验收标准

```yaml
功能:
  - [ ] PDF 文档功能已移除
  - [ ] 素材库支持文件夹管理
  - [ ] 可以选择知识库范围
  - [ ] RAG 检索根据选择过滤

UI:
  - [ ] 文件夹树形结构清晰
  - [ ] 知识库选择器易用
  - [ ] 操作流畅

兼容性:
  - [ ] 现有文件迁移到根目录
  - [ ] PDF 解析功能正常
```

## 文件路径

```
frontend/src/
  ├─ pages/
  │   ├─ MaterialLibraryPage.tsx    ← 重构
  │   └─ PDFDocumentsPage.tsx       ← 删除
  ├─ components/
  │   ├─ MaterialLibrary/
  │   │   ├─ FolderTree.tsx         ← 新增
  │   │   ├─ FileList.tsx           ← 新增
  │   │   └─ KnowledgeScopeSelector.tsx  ← 新增
  │   └─ PDFDocument*               ← 删除
  └─ App.tsx                        ← 更新路由

backend/app/
  ├─ api/
  │   ├─ folders.py                 ← 新增
  │   └─ materials.py               ← 更新
  └─ services/
      └─ rag_service.py             ← 更新（支持知识库过滤）
```

## 参考

**Get 笔记知识库选择**:
```tsx
// 类似这样的 UI
<KnowledgeSelector>
  <SearchBar placeholder="搜索知识库" />
  <CategoryList>
    <Category name="工艺文件" checked />
    <Category name="技术标准" />
    <Category name="培训资料" />
  </CategoryList>
  <SelectedCount>已选择 2 个知识库</SelectedCount>
</KnowledgeSelector>
```

## 注意事项

1. 保持现有文件数据
2. 文件夹数据结构可扩展
3. 知识库选择要持久化
4. 移动端适配

## 工作目录
D:\Project Nantianmen\projects\localknowledgebase-word

## 预期效果
- 功能清晰（无冗余）
- 文件管理有序
- 知识库选择灵活
