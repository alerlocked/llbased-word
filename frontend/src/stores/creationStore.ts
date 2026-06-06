import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { pdfService, PDFDocument, PDFDocumentView } from '../services/pdfService'
import type { StructuredDocument } from '../types/template'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  steps?: any[]
  isStreaming?: boolean
  /** Progress text shown while waiting for content (e.g. "正在分析...") */
  progressText?: string
}

export interface ChatSession {
  id: string
  title: string
  messages: Message[]
  timestamp: number
}

/** 编辑历史记录 - 用于撤销功能 */
export interface EditRecord {
  id: string
  projectId: number
  type: 'replace' | 'insert' | 'append'
  /** 修改前的内容（用于回滚） */
  originalContent: string
  /** 修改后的内容 */
  newContent: string
  /** 修改位置 [start, end] */
  position: [number, number]
  timestamp: number
}

interface ProjectState {
  editorContent: string
  sessions: ChatSession[]
  activeSessionId: string | null
  lastSavedContent: string
  // 保持旧字段以兼容正在迁移中的状态
  chatHistory?: Message[] 
}

interface PDFState {
  pdfDocuments: PDFDocument[];
  currentPDFDocument: PDFDocumentView | null;
  pdfLoading: boolean;
  pdfError: string | null;
  pdfDrawerVisible: boolean;
}

interface CreationStore extends PDFState {
  projects: Record<number, ProjectState>
  setEditorContent: (projectId: number, content: string) => void
  getProjectState: (projectId: number) => ProjectState

  // Template-driven editor state
  editorTemplateData: StructuredDocument | null
  editorContentFormat: 'markdown' | 'template'
  setEditorTemplateData: (data: StructuredDocument | null) => void
  setEditorContentFormat: (format: 'markdown' | 'template') => void

  // 会话管理
  createNewSession: (projectId: number, title?: string) => string
  deleteSession: (projectId: number, sessionId: string) => void
  switchSession: (projectId: number, sessionId: string) => void
  updateSessionMessages: (projectId: number, sessionId: string, messages: Message[]) => void

  clearProjectState: (projectId: number) => void

  // 编辑历史管理
  editHistory: EditRecord[]
  /** 记录一次编辑操作 */
  pushEdit: (record: Omit<EditRecord, 'id' | 'timestamp'>) => void
  /** 撤销上一次编辑 */
  undo: (projectId: number) => string | null
  /** 是否可以撤销 */
  canUndo: (projectId: number) => boolean
  /** 清空编辑历史 */
  clearEditHistory: (projectId: number) => void

  // PDF相关操作
  loadPDFDocuments: () => Promise<void>;
  loadPDFDocument: (docId: string) => Promise<void>;
  reExtractPDFDocument: (docId: string) => Promise<void>;
  setPDFDrawerVisible: (visible: boolean) => void;
  clearPDFError: () => void;
}

const defaultProjectState: ProjectState = {
  editorContent: '',
  sessions: [],
  activeSessionId: null,
  lastSavedContent: ''
}

export const useCreationStore = create<CreationStore>()(
  persist(
    (set, get) => ({
      // PDF相关状态
      pdfDocuments: [],
      currentPDFDocument: null,
      pdfLoading: false,
      pdfError: null,
      pdfDrawerVisible: false,

      projects: {},
      editHistory: [],

      // Template-driven editor state
      editorTemplateData: null,
      editorContentFormat: 'markdown',

      setEditorTemplateData: (data) => set({ editorTemplateData: data }),
      setEditorContentFormat: (format) => set({ editorContentFormat: format }),

      getProjectState: (projectId: number) => {
        const state = get()
        let project = state.projects[projectId]
        
        if (!project) {
          project = { ...defaultProjectState }
        }

        // 数据迁移与初始化逻辑
        let needsUpdate = false
        const updatedProject = { ...project }

        // 1. 如果有旧的 chatHistory 且 sessions 为空，进行迁移
        if (project.chatHistory && project.chatHistory.length > 0 && project.sessions.length === 0) {
          const migrationSessionId = `session_migrated_${Date.now()}`
          updatedProject.sessions = [{
            id: migrationSessionId,
            title: '迁移对话',
            messages: project.chatHistory,
            timestamp: Date.now()
          }]
          updatedProject.activeSessionId = migrationSessionId
          delete updatedProject.chatHistory
          needsUpdate = true
        }

        // 2. 如果 sessions 仍为空，初始化首个会话
        if (updatedProject.sessions.length === 0) {
          const newSessionId = `session_${Date.now()}`
          updatedProject.sessions = [{
            id: newSessionId,
            title: '新对话',
            messages: [],
            timestamp: Date.now()
          }]
          updatedProject.activeSessionId = newSessionId
          needsUpdate = true
        }

        // 3. 确保 activeSessionId 合法
        if (!updatedProject.activeSessionId || !updatedProject.sessions.find(s => s.id === updatedProject.activeSessionId)) {
          updatedProject.activeSessionId = updatedProject.sessions[0].id
          needsUpdate = true
        }

        if (needsUpdate) {
          // 注意：在 get 中直接 set 可能会引发 React 警告，但对于 persist 的初始化是安全的
          // 更好的做法是在组件渲染时通过 useEffect 处理，但这里为了鲁棒性放在 get 中
          setTimeout(() => {
            set((s) => ({
              projects: {
                ...s.projects,
                [projectId]: updatedProject
              }
            }))
          }, 0)
        }

        return updatedProject
      },

      setEditorContent: (projectId: number, content: string) => {
        set((state) => ({
          projects: {
            ...state.projects,
            [projectId]: {
              ...(state.projects[projectId] || defaultProjectState),
              editorContent: content
            }
          }
        }))
      },

      createNewSession: (projectId: number, title: string = '新对话') => {
        const newSessionId = `session_${Date.now()}`
        const newSession: ChatSession = {
          id: newSessionId,
          title,
          messages: [],
          timestamp: Date.now()
        }

        set((state) => {
          const project = state.projects[projectId] || { ...defaultProjectState }
          return {
            projects: {
              ...state.projects,
              [projectId]: {
                ...project,
                sessions: [newSession, ...project.sessions],
                activeSessionId: newSessionId
              }
            }
          }
        })
        return newSessionId
      },

      deleteSession: (projectId: number, sessionId: string) => {
        set((state) => {
          const project = state.projects[projectId] || { ...defaultProjectState }
          const newSessions = project.sessions.filter(s => s.id !== sessionId)
          
          // 如果删完了，自动创建一个
          if (newSessions.length === 0) {
            const newId = `session_${Date.now()}`
            newSessions.push({
              id: newId,
              title: '新对话',
              messages: [],
              timestamp: Date.now()
            })
          }

          let newActiveId = project.activeSessionId
          if (sessionId === project.activeSessionId) {
            newActiveId = newSessions[0].id
          }

          return {
            projects: {
              ...state.projects,
              [projectId]: {
                ...project,
                sessions: newSessions,
                activeSessionId: newActiveId
              }
            }
          }
        })
      },

      switchSession: (projectId: number, sessionId: string) => {
        set((state) => ({
          projects: {
            ...state.projects,
            [projectId]: {
              ...(state.projects[projectId] || defaultProjectState),
              activeSessionId: sessionId
            }
          }
        }))
      },

      updateSessionMessages: (projectId: number, sessionId: string, messages: Message[]) => {
        set((state) => {
          const project = state.projects[projectId] || { ...defaultProjectState }
          const newSessions = project.sessions.map(s => {
            if (s.id === sessionId) {
              // 自动更新标题：取第一条用户消息
              let newTitle = s.title
              const firstUserMsg = messages.find(m => m.role === 'user')
              if (firstUserMsg && (s.title === '新对话' || s.title === '迁移对话')) {
                newTitle = firstUserMsg.content.slice(0, 15) + (firstUserMsg.content.length > 15 ? '...' : '')
              }
              return { ...s, messages, title: newTitle }
            }
            return s
          })

          return {
            projects: {
              ...state.projects,
              [projectId]: {
                ...project,
                sessions: newSessions
              }
            }
          }
        })
      },

      clearProjectState: (projectId: number) => {
        set((state) => {
          const newProjects = { ...state.projects }
          delete newProjects[projectId]
          return { projects: newProjects }
        })
      },

      // 编辑历史管理
      pushEdit: (record) => {
        const newRecord: EditRecord = {
          ...record,
          id: `edit_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          timestamp: Date.now()
        }
        set((state) => ({
          editHistory: [...state.editHistory, newRecord].slice(-50) // 最多保留50条
        }))
      },

      undo: (projectId: number) => {
        const state = get()
        // 找到该项目最近的一条编辑记录
        const projectHistory = state.editHistory.filter(r => r.projectId === projectId)
        if (projectHistory.length === 0) return null

        const lastEdit = projectHistory[projectHistory.length - 1]
        const project = state.projects[projectId]
        if (!project) return null

        // 回滚编辑器内容
        const currentContent = project.editorContent
        const [start, _end] = lastEdit.position
        
        // 计算当前插入内容的长度（用于正确定位删除范围）
        const insertedLength = lastEdit.newContent.length
        const restoredContent = 
          currentContent.slice(0, start) + 
          lastEdit.originalContent + 
          currentContent.slice(start + insertedLength)

        // 更新状态
        set((s) => ({
          projects: {
            ...s.projects,
            [projectId]: {
              ...s.projects[projectId],
              editorContent: restoredContent
            }
          },
          editHistory: s.editHistory.filter(r => r.id !== lastEdit.id)
        }))

        return restoredContent
      },

      canUndo: (projectId: number) => {
        const state = get()
        return state.editHistory.some(r => r.projectId === projectId)
      },

      clearEditHistory: (projectId: number) => {
        set((state) => ({
          editHistory: state.editHistory.filter(r => r.projectId !== projectId)
        }))
      },

      // PDF相关操作
      loadPDFDocuments: async () => {
        set({ pdfLoading: true, pdfError: null });
        try {
          const result = await pdfService.listDocuments();
          set({ pdfDocuments: result.documents, pdfLoading: false });
        } catch (error: any) {
          set({ pdfError: error.message, pdfLoading: false });
        }
      },

      loadPDFDocument: async (docId: string) => {
        set({ pdfLoading: true, pdfError: null });
        try {
          const viewData = await pdfService.getDocumentView(docId);
          set({ currentPDFDocument: viewData, pdfLoading: false });
        } catch (error: any) {
          set({ pdfError: error.message, pdfLoading: false });
        }
      },

      reExtractPDFDocument: async (docId: string): Promise<void> => {
        set({ pdfLoading: true, pdfError: null });
        try {
          await pdfService.reExtractDocument(docId);
          // 重新加载文档
          await get().loadPDFDocument(docId);
          set({ pdfLoading: false });
        } catch (error: any) {
          set({ pdfError: error.message, pdfLoading: false });
          throw error;
        }
      },

      setPDFDrawerVisible: (visible: boolean) => set({ pdfDrawerVisible: visible }),
      clearPDFError: () => set({ pdfError: null }),
    }),
    {
      name: 'creation-storage-v2', // 升级版本号以隔离旧的不兼容存储
      version: 2
    }
  )
)
