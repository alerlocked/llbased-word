import Dexie, { Table } from 'dexie'

/**
 * IndexedDB数据库定义
 * 工艺文件辅助编辑系统 - 本地存储
 */

// 文档素材记录
export interface MaterialRecord {
  id?: number
  name: string
  type: string // pdf, docx, txt
  content: string
  projectId?: number
  createdAt: Date
}

// 项目记录
export interface ProjectRecord {
  id?: number
  name: string
  description?: string
  createdAt: Date
}

// 知识卡片
export interface KnowledgeCardRecord {
  id?: number
  materialId: number
  entity: string // 实体名称
  entityType: 'time' | 'location' | 'person' | 'organization' | 'terminology'
  description: string // 简要说明
  sources: KnowledgeSource[]
  createdAt: Date
}

// 知识来源
export interface KnowledgeSource {
  title: string
  url: string
  credibility: 'high' | 'medium' | 'low'
}

// 编辑历史记录
export interface EditorHistoryRecord {
  id?: number
  projectId: number
  content: string
  operation: string // ai_draft, ai_rewrite, manual_edit
  createdAt: Date
}

/**
 * 数据库类定义
 */
class CraftDocumentDatabase extends Dexie {
  materials!: Table<MaterialRecord>
  projects!: Table<ProjectRecord>
  knowledgeCards!: Table<KnowledgeCardRecord>
  editorHistory!: Table<EditorHistoryRecord>

  constructor() {
    super('CraftDocumentDB')

    // 定义数据库版本和表结构
    this.version(1).stores({
      materials: '++id, name, type, projectId, createdAt',
      projects: '++id, name, createdAt',
      knowledgeCards: '++id, materialId, entity, entityType, createdAt',
      editorHistory: '++id, projectId, operation, createdAt',
    })
  }
}

// 导出数据库实例
export const db = new CraftDocumentDatabase()
