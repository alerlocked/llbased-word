# 前后端 API 对齐文档

**项目**: 智能工艺文件辅助编辑系统  
**版本**: v1.0  
**更新日期**: 2026-03-07

---

## 1. API 规范

### 1.1 基础信息
- **后端地址**: `http://localhost:8000`
- **API 前缀**: `/api`
- **数据格式**: JSON
- **认证方式**: 暂无 (后续可添加 JWT)

### 1.2 响应格式
```typescript
// 成功响应
{
  "success": true,
  "data": any,
  "message": "操作成功"
}

// 错误响应
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": any
  }
}
```

---

## 2. 文档管理 API

### 2.1 获取文档列表
```http
GET /api/documents
```

**响应示例**:
```json
{
  "items": [
    {
      "id": "全单电缆装配规程",
      "name": "全单电缆装配规程",
      "type": "pdf",
      "page_count": 44,
      "has_html": true,
      "created_at": "2026-02-24T00:00:00Z",
      "updated_at": "2026-02-24T00:00:00Z"
    }
  ],
  "total": 1
}
```

**前端调用**:
```typescript
// frontend/src/services/documentService.ts
export async function getDocuments() {
  const response = await fetch(`${API_BASE_URL}/api/documents`);
  return response.json();
}
```

---

### 2.2 获取文档详情
```http
GET /api/documents/{doc_id}
```

**路径参数**:
- `doc_id`: 文档 ID (string)

**响应示例**:
```json
{
  "id": "全单电缆装配规程",
  "name": "全单电缆装配规程",
  "type": "pdf",
  "page_count": 44,
  "has_html": true,
  "tables": 44,
  "created_at": "2026-02-24T00:00:00Z"
}
```

---

### 2.3 获取文档表格列表
```http
GET /api/documents/{doc_id}/tables
```

**响应示例**:
```json
{
  "items": [
    {
      "index": 0,
      "page": 1,
      "rows": 10,
      "cols": 5,
      "has_html": true,
      "preview": "表格内容预览..."
    }
  ],
  "total": 44
}
```

**前端调用**:
```typescript
// frontend/src/services/documentService.ts
export async function getDocumentTables(docId: string) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${docId}/tables`);
  return response.json();
}
```

---

### 2.4 获取表格 HTML
```http
GET /api/documents/{doc_id}/tables/{table_index}/html
```

**路径参数**:
- `doc_id`: 文档 ID
- `table_index`: 表格索引 (0-based)

**响应**:
- Content-Type: `text/html; charset=utf-8`
- 直接返回 HTML 字符串

**前端调用**:
```typescript
export async function getTableHtml(docId: string, tableIndex: number) {
  const response = await fetch(
    `${API_BASE_URL}/api/documents/${docId}/tables/${tableIndex}/html`
  );
  return response.text(); // 注意：返回文本，不是 JSON
}
```

---

### 2.5 转换 PDF 为 HTML
```http
POST /api/process-documents/{doc_id}/convert-html?backend=vlm-auto-engine
```

**路径参数**:
- `doc_id`: 文档 ID

**查询参数**:
- `backend`: 解析后端 (`vlm-auto-engine` | `pipeline`)

**响应示例**:
```json
{
  "success": true,
  "message": "转换成功",
  "data": {
    "output_path": "exports_vlm_full/全单电缆装配规程_complete.html",
    "pages": 44,
    "images": 51
  }
}
```

**前端调用**:
```typescript
export async function convertPdfToHtml(docId: string, backend = 'vlm-auto-engine') {
  const response = await fetch(
    `${API_BASE_URL}/api/process-documents/${docId}/convert-html?backend=${backend}`,
    { method: 'POST' }
  );
  return response.json();
}
```

---

## 3. 创作管理 API

### 3.1 获取项目列表
```http
GET /api/creation/projects
```

**响应示例**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "工艺规程 v1.0",
      "created_at": "2026-03-05T08:00:00Z",
      "updated_at": "2026-03-07T09:00:00Z",
      "status": "active"
    }
  ],
  "total": 1
}
```

**前端调用**:
```typescript
// frontend/src/pages/WorkspacePage.tsx (已实现)
const fetchProjects = async () => {
  const response = await fetch('http://localhost:8000/api/creation/projects');
  if (response.ok) {
    const data = await response.json();
    setProjects(data.items || data);
  }
};
```

---

### 3.2 创建项目
```http
POST /api/creation/projects
```

**请求体**:
```json
{
  "name": "新工艺规程"
}
```

**响应示例**:
```json
{
  "id": 2,
  "name": "新工艺规程",
  "created_at": "2026-03-07T09:30:00Z",
  "status": "active"
}
```

**前端调用**:
```typescript
export async function createProject(name: string) {
  const response = await fetch(`${API_BASE_URL}/api/creation/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  return response.json();
}
```

---

### 3.3 获取项目内容
```http
GET /api/creation/projects/{project_id}/content
```

**路径参数**:
- `project_id`: 项目 ID (number)

**响应示例**:
```json
{
  "content": "# 工艺规程\n\n## 1. 总则\n\n内容...",
  "format": "markdown"
}
```

**前端调用**:
```typescript
// frontend/src/pages/WorkspacePage.tsx (已实现)
const fetchProjectContent = async (projectId: number) => {
  const response = await fetch(
    `http://localhost:8000/api/creation/projects/${projectId}/content`
  );
  if (response.ok) {
    const data = await response.json();
    setEditorContent(data.content || '');
  }
};
```

---

### 3.4 保存项目内容
```http
PUT /api/creation/projects/{project_id}/content
```

**路径参数**:
- `project_id`: 项目 ID

**请求体**:
```json
{
  "content": "# 工艺规程\n\n## 1. 总则\n\n修改后的内容...",
  "format": "markdown"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "保存成功",
  "updated_at": "2026-03-07T09:35:00Z"
}
```

**前端调用**:
```typescript
// frontend/src/pages/WorkspacePage.tsx (已实现)
const saveProjectContent = async (projectId: number, content: string) => {
  const response = await fetch(
    `http://localhost:8000/api/creation/projects/${projectId}/content`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, format: 'markdown' })
    }
  );
  return response.json();
};
```

---

### 3.5 删除项目
```http
DELETE /api/creation/projects/{project_id}
```

**响应示例**:
```json
{
  "success": true,
  "message": "删除成功"
}
```

---

## 4. RAG 检索 API

### 4.1 知识库检索
```http
POST /api/rag/search
```

**请求体**:
```json
{
  "query": "电缆装配标准",
  "top_k": 5,
  "threshold": 0.7
}
```

**响应示例**:
```json
{
  "results": [
    {
      "content": "电缆装配相关内容...",
      "source": "全单电缆装配规程",
      "page": 10,
      "score": 0.92
    }
  ],
  "total": 5
}
```

**前端调用**:
```typescript
export async function searchKnowledge(query: string, topK = 5) {
  const response = await fetch(`${API_BASE_URL}/api/rag/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK })
  });
  return response.json();
}
```

---

## 5. Agent API

### 5.1 智能助手对话
```http
POST /api/agent/chat
```

**请求体**:
```json
{
  "message": "帮我优化这段工艺描述",
  "context": {
    "project_id": 1,
    "selected_text": "当前选中的文本"
  }
}
```

**响应示例** (流式):
```json
{
  "type": "stream",
  "content": "好的，我来帮你优化..."
}
```

**前端调用** (流式):
```typescript
export async function chatWithAgent(message: string, context: any) {
  const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, context })
  });
  
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    // 处理流式数据
    console.log(chunk);
  }
}
```

---

### 5.2 术语对齐
```http
POST /api/agent/terminology/align
```

**请求体**:
```json
{
  "text": "将导线连接到端子",
  "mode": "standardize"
}
```

**响应示例**:
```json
{
  "aligned_text": "将导线连接至接线端子",
  "mappings": [
    {
      "original": "到",
      "standard": "至",
      "confidence": 0.95
    }
  ],
  "score": 95
}
```

---

### 5.3 合规检查
```http
POST /api/agent/compliance/check
```

**请求体**:
```json
{
  "content": "工艺文件内容...",
  "level": "standard",
  "standards": ["企业标准", "安全标准"]
}
```

**响应示例**:
```json
{
  "score": 81.82,
  "issues": [
    {
      "type": "warning",
      "message": "缺少安全警示标识",
      "line": 15,
      "suggestion": "建议在危险操作前添加⚠️标识"
    }
  ],
  "passed": false
}
```

---

## 6. 前端服务层封装

### 6.1 API Client
```typescript
// frontend/src/services/apiClient.ts
const API_BASE_URL = 'http://localhost:8000';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  }

  async post<T>(path: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  }

  async put<T>(path: string, data: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  }

  async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'DELETE'
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  }
}

export const apiClient = new ApiClient();
```

### 6.2 服务层示例
```typescript
// frontend/src/services/documentService.ts
import { apiClient } from './apiClient';

export interface Document {
  id: string;
  name: string;
  type: string;
  page_count: number;
  has_html: boolean;
  created_at: string;
  updated_at: string;
}

export interface Table {
  index: number;
  page: number;
  rows: number;
  cols: number;
  has_html: boolean;
  preview: string;
}

export const documentService = {
  async getDocuments() {
    return apiClient.get<{ items: Document[]; total: number }>('/api/documents');
  },

  async getDocument(docId: string) {
    return apiClient.get<Document>(`/api/documents/${docId}`);
  },

  async getTables(docId: string) {
    return apiClient.get<{ items: Table[]; total: number }>(
      `/api/documents/${docId}/tables`
    );
  },

  async getTableHtml(docId: string, tableIndex: number) {
    const response = await fetch(
      `${apiClient['baseUrl']}/api/documents/${docId}/tables/${tableIndex}/html`
    );
    return response.text();
  },

  async convertPdfToHtml(docId: string, backend = 'vlm-auto-engine') {
    return apiClient.post(
      `/api/process-documents/${docId}/convert-html?backend=${backend}`,
      {}
    );
  }
};
```

---

## 7. 状态管理对齐

### 7.1 Zustand Store
```typescript
// frontend/src/stores/creationStore.ts
import { create } from 'zustand';

interface ProjectState {
  editorContent: string;
  lastSaved: string;
  isDirty: boolean;
}

interface CreationStore {
  projects: Map<number, ProjectState>;
  
  // Actions
  setEditorContent: (projectId: number, content: string) => void;
  getProjectState: (projectId: number) => ProjectState;
  markSaved: (projectId: number) => void;
}

export const useCreationStore = create<CreationStore>((set, get) => ({
  projects: new Map(),

  setEditorContent: (projectId, content) => {
    set((state) => {
      const newProjects = new Map(state.projects);
      const existing = newProjects.get(projectId) || {
        editorContent: '',
        lastSaved: '',
        isDirty: false
      };
      newProjects.set(projectId, {
        ...existing,
        editorContent: content,
        isDirty: true
      });
      return { projects: newProjects };
    });
  },

  getProjectState: (projectId) => {
    return get().projects.get(projectId) || {
      editorContent: '',
      lastSaved: '',
      isDirty: false
    };
  },

  markSaved: (projectId) => {
    set((state) => {
      const newProjects = new Map(state.projects);
      const existing = newProjects.get(projectId);
      if (existing) {
        newProjects.set(projectId, {
          ...existing,
          lastSaved: new Date().toISOString(),
          isDirty: false
        });
      }
      return { projects: newProjects };
    });
  }
}));
```

---

## 8. 错误处理

### 8.1 统一错误处理
```typescript
// frontend/src/utils/errorHandler.ts
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public details?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function handleApiError(error: unknown) {
  if (error instanceof ApiError) {
    message.error(`[${error.code}] ${error.message}`);
    console.error('API Error Details:', error.details);
  } else if (error instanceof Error) {
    message.error(error.message);
    console.error('Error:', error);
  } else {
    message.error('未知错误');
    console.error('Unknown Error:', error);
  }
}
```

### 8.2 使用示例
```typescript
import { handleApiError } from '@/utils/errorHandler';

try {
  const data = await documentService.getDocuments();
  setDocuments(data.items);
} catch (error) {
  handleApiError(error);
}
```

---

## 9. 测试对齐

### 9.1 后端测试
```python
# backend/tests/api/test_documents.py
def test_get_documents(client):
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
```

### 9.2 前端测试
```typescript
// frontend/src/__tests__/services/documentService.test.ts
import { documentService } from '@/services/documentService';

test('should fetch documents', async () => {
  const data = await documentService.getDocuments();
  expect(data.items).toBeDefined();
  expect(data.total).toBeGreaterThanOrEqual(0);
});
```

---

## 10. 下一步行动

### 10.1 已完成 ✅
- [x] 创建蓝白灰设计系统
- [x] 定义 API 规范
- [x] 编写 API 对齐文档

### 10.2 待完成 ⏳
- [ ] 更新前端组件使用新设计系统
- [ ] 完善前端服务层封装
- [ ] 添加 API 测试用例
- [ ] 实现错误边界处理
- [ ] 优化加载状态
- [ ] 添加请求缓存

---

**文档版本**: v1.0  
**最后更新**: 2026-03-07 09:35
