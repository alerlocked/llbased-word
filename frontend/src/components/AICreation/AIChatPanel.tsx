/**
 * AIChatPanel - AI交互面板
 * 上方：对话历史 | 下方：输入框和快捷操作
 * 温暖黄色系视觉风格
 */
import { useState, useEffect, useRef } from 'react'
import { Input, Button, Space, message, Spin, Drawer, List, Typography, Popconfirm, Collapse, Upload, Tag, Modal } from 'antd'
import { CopyOutlined, PlusOutlined, RocketOutlined, HistoryOutlined, DeleteOutlined, MenuFoldOutlined, MessageOutlined, StopOutlined, PaperClipOutlined, CloseOutlined, FileTextOutlined } from '@ant-design/icons'
import { useCreationStore, Message } from '../../stores/creationStore'
import { colors } from '../../styles/design-tokens'
import { PlanOptionCard } from './PlanOptionCard'
import { AgentCollaborationView } from './AgentCollaborationView'
import { PlanOption, AgentCallEvent, CollaborationEvent } from '../../services/conversationService'
import { SolutionList } from './SolutionList'
import { ImprovementSolution } from './SolutionCard'
import { structuredDocToSections } from '../../utils/templateTransform'
import type { StructuredDocument } from '../../types/template'

const { TextArea } = Input
const { Text } = Typography

interface AIChatPanelProps {
  projectId: number | null
  selectedText: string
  onInsertToEditor: (content: string) => void
  onDirectInsert?: (content: string) => void
  /** 智能写作结果预览回调 - 在主编辑器中显示 InlineDiff */
  onPreviewContent?: (newContent: string) => void
  /** 关闭面板回调 */
  onClose?: () => void
  /** 选中的素材列表 - 用于注入AI上下文 */
  selectedMaterials?: Array<{
    id: string | number
    name: string
    content: string
    type: string
  }>
  /** 清除选区引用（点引用标签 × 时调用） */
  onClearSelectedText?: () => void
  /** N6 gate: true when the project working area has no material selected —
   *  AI input is locked until the user picks materials (no silent full retrieval) */
  workingAreaEmpty?: boolean
  /** Open the material library panel (used by the gate modal's CTA) */
  onOpenMaterials?: () => void
}

const AIChatPanel: React.FC<AIChatPanelProps> = ({
  projectId,
  selectedText,
  onInsertToEditor,
  onDirectInsert,
  onPreviewContent,
  onClose,
  selectedMaterials = [],
  onClearSelectedText,
  workingAreaEmpty = false,
  onOpenMaterials,
}) => {
  const { 
    getProjectState, 
    createNewSession, 
    deleteSession, 
    switchSession, 
    updateSessionMessages 
  } = useCreationStore()
  
  // 获取项目状态，增加空保护
  const projectState = projectId ? getProjectState(projectId) : null
  const sessions = projectState?.sessions || []
  const activeSessionId = projectState?.activeSessionId
  const activeSession = sessions.find(s => s.id === activeSessionId) || (sessions.length > 0 ? sessions[0] : null)
  const messages = activeSession?.messages || []

  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  // N6 gate modal: shown when the user tries to type/send with an empty working area
  const [gateModalOpen, setGateModalOpen] = useState(false)
  // 'fill' = fill missing chapters (empty doc auto-falls-back to full generation on the
  // backend), null = free chat. 'generate' union kept for backend contract compat.
  const [generationMode, setGenerationMode] = useState<'generate' | 'fill' | null>(null)
  const [historyVisible, setHistoryVisible] = useState(false)
  // Uploaded file state for AI context injection — persisted in sessionStorage
  // so it survives page refresh within the same tab/session
  const UPLOAD_STORAGE_KEY = 'ai_uploaded_file'
  const [uploadedFile, setUploadedFileState] = useState<{
    name: string
    content: string
    charCount: number
    status: 'uploading' | 'done' | 'error'
  } | null>(() => {
    try {
      const stored = sessionStorage.getItem(UPLOAD_STORAGE_KEY)
      return stored ? JSON.parse(stored) : null
    } catch { return null }
  })

  // Wrapper that also persists to sessionStorage
  const setUploadedFile = (val: React.SetStateAction<typeof uploadedFile>) => {
    setUploadedFileState(prev => {
      const next = typeof val === 'function' ? val(prev) : val
      if (next && next.status === 'done') {
        sessionStorage.setItem(UPLOAD_STORAGE_KEY, JSON.stringify(next))
      } else {
        sessionStorage.removeItem(UPLOAD_STORAGE_KEY)
      }
      return next
    })
  }
  // 流式读取控制器，用于停止生成
  const [streamController, setStreamController] = useState<AbortController | null>(null)
  // 保存用户原始输入，用于停止时恢复
  const [originalInput, setOriginalInput] = useState<string>('')
  // 当前模式（qa 或 write）- 使用 useRef 避免异步更新问题
  const currentModeRef = useRef<'qa' | 'write'>('write')
  // Editor content from AI response (content after ---EDITOR--- marker)
  const editorContentRef = useRef<string>('')
  
  // 计划选项相关状态
  const [planOptions, setPlanOptions] = useState<PlanOption[]>([])
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [currentSessionIdForPlan, setCurrentSessionIdForPlan] = useState<string | null>(null)
  
  // 改进方案相关状态
  const [improvementSolutions, setImprovementSolutions] = useState<ImprovementSolution[]>([])
  const [currentSessionIdForSolution, setCurrentSessionIdForSolution] = useState<string | null>(null)
  
  // Agent协作相关状态
  const [agentCalls, setAgentCalls] = useState<AgentCallEvent[]>([])
  const [collaborationHistory, setCollaborationHistory] = useState<CollaborationEvent[]>([])
  
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 辅助：更新当前会话消息
  const updateActiveMessages = (newMsgs: Message[]) => {
    if (projectId && activeSession?.id) {
      updateSessionMessages(projectId, activeSession.id, newMsgs)
    }
  }

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 待办事项现在直接显示在消息气泡内，不需要单独的状态管理

  // 处理选择计划
  const handleSelectPlan = async (planId: string, sessionId: string | null) => {
    if (!planId || !sessionId) {
      message.warning('请先选择计划')
      return
    }

    const userMsg: Message = {
      role: 'user',
      content: `已选择方案：${planId}`,
      timestamp: Date.now()
    }
    
    let assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    }

    const nextMessages = [...messages, userMsg, assistantMsg]
    updateActiveMessages(nextMessages)
    setLoading(true)

    let contentAccumulator = ''

    try {
      const response = await fetch('http://localhost:8000/api/agent/select-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          plan_option_id: planId
        })
      })

      if (!response.ok) throw new Error('选择计划请求失败')

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('无法读取流')

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n\n')
          
          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data: ')) continue
            
            try {
              const dataStr = line.slice(6).trim()
              if (dataStr === '[DONE]') break
              
              const data = JSON.parse(dataStr)
              if (data.type === 'plan_options') {
                // 再次收到计划选项
                const options = Array.isArray(data.plan_options) ? data.plan_options : []
                setPlanOptions(options)
                setCurrentSessionIdForPlan(data.session_id || sessionId)
                
                contentAccumulator = options.length > 0
                  ? `已生成 ${options.length} 个写作方案，请选择其中一个：`
                  : '等待生成方案...'

                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  isStreaming: false,
                  planOptions: options,
                  sessionId: data.session_id || sessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                setStreamController(null)
                return
              } else if (data.type === 'agent_call') {
                // Record agent collaboration
                const agentCallData = data as AgentCallEvent
                setAgentCalls(prev => [...prev, agentCallData])
                const callMessage = `${agentCallData.caller} → ${agentCallData.target_agent}: ${agentCallData.reason}`
                contentAccumulator += `\n\n[协作] ${callMessage}`
              } else if (data.type === 'collaboration') {
                const collaborationData = data as CollaborationEvent
                setCollaborationHistory(prev => [...prev, collaborationData])
                if (collaborationData.call_stack.length > 0) {
                  const stackInfo = `调用链: ${collaborationData.call_stack.join(' → ')}`
                  contentAccumulator += `\n\n[协作链] ${stackInfo}`
                }
              } else if (data.type === 'progress') {
                // Update progress text so user sees what's happening
                assistantMsg = { ...assistantMsg, progressText: data.message || '' }
              } else if (data.type === 'result') {
                contentAccumulator = data.content
                if (data.has_editor && data.editor_content) {
                  editorContentRef.current = data.editor_content
                } else {
                  editorContentRef.current = ''
                }
              } else if (data.type === 'error') {
                contentAccumulator += `\n[错误] ${data.error}`
              } else if (data.type === 'warning') {
                // Per-chapter row-gap warnings (e.g. G25a rows left empty after retries)
                contentAccumulator += `\n⚠ ${data.message || ''}\n`
              }

              const updatedAssistant: Message = {
                ...assistantMsg,
                content: contentAccumulator,
                isStreaming: data.type !== 'result' && data.type !== 'error',
                progressText: data.type === 'progress' ? (data.message || '') : undefined,
              }
              updateActiveMessages([...messages, userMsg, updatedAssistant])
            } catch (e) {
              console.error('SSE Error:', e)
            }
          }
        }
      } catch (readError) {
        const err = readError as any
        if (err.name === 'AbortError') {
          const stoppedMsg: Message = {
            ...assistantMsg,
            content: contentAccumulator || '[已停止]',
            isStreaming: false
          }
          updateActiveMessages([...messages, userMsg, stoppedMsg])
          return
        }
        throw readError
      }

      setLoading(false)
      setStreamController(null)
    } catch (error) {
      const err = error as any
      if (err.name === 'AbortError') {
        return
      }
      message.error(`选择计划失败: ${err.message}`)
      setLoading(false)
      setStreamController(null)
    }
  }

  // 处理用户回复询问问题
  const handleReplyQuestion = async (sessionId: string, answer: string) => {
    if (!answer.trim() || !sessionId) return

    const userMsg: Message = {
      role: 'user',
      content: answer,
      timestamp: Date.now()
    }
    
    let assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    }

    const nextMessages = [...messages, userMsg, assistantMsg]
    updateActiveMessages(nextMessages)
    setInputText('')
    setLoading(true)

    let contentAccumulator = ''

    const controller = new AbortController()
    setStreamController(controller)

    try {
      const response = await fetch('http://localhost:8000/api/agent/reply-question-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          answer: answer
        }),
        signal: controller.signal
      })

      if (!response.ok) throw new Error('回复请求失败')

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('无法读取流')

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n\n')
          
          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data: ')) continue
            
            try {
              const dataStr = line.slice(6).trim()
              if (dataStr === '[DONE]') break
              
              const data = JSON.parse(dataStr)
              if (data.type === 'pending_questions') {
                // 再次收到询问问题
                const questions = Array.isArray(data.questions) ? data.questions : []
                const questionsText = questions.map((q: any, idx: number) => 
                  `${idx + 1}. ${q.question || q.text || ''}`
                ).join('\n')
                
                contentAccumulator = questions.length > 0
                  ? `需要补充以下信息：\n\n${questionsText}\n\n请在下方输入框中输入您的回答。`
                  : '等待用户补充信息...'

                const newSessionId = data.session_id || sessionId
                if (newSessionId) {
                  (window as any).__current_session_id = newSessionId
                }

                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  isStreaming: false,
                  pendingQuestions: questions,
                  sessionId: newSessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                setStreamController(null)
                return
              } else if (data.type === 'progress') {
                assistantMsg = { ...assistantMsg, progressText: data.message || '' }
              } else if (data.type === 'result') {
                contentAccumulator = data.content
                if (data.has_editor && data.editor_content) {
                  editorContentRef.current = data.editor_content
                } else {
                  editorContentRef.current = ''
                }
              } else if (data.type === 'error') {
                contentAccumulator += `\n[错误] ${data.error}`
              } else if (data.type === 'warning') {
                // Per-chapter row-gap warnings (e.g. G25a rows left empty after retries)
                contentAccumulator += `\n⚠ ${data.message || ''}\n`
              }

              const updatedAssistant: Message = {
                ...assistantMsg,
                content: contentAccumulator,
                isStreaming: data.type !== 'result' && data.type !== 'error',
                progressText: data.type === 'progress' ? (data.message || '') : undefined,
              }
              updateActiveMessages([...messages, userMsg, updatedAssistant])
            } catch (e) {
              console.error('SSE Error:', e)
            }
          }
        }
      } catch (readError) {
        const err = readError as any
        if (err.name === 'AbortError' || controller.signal.aborted) {
          const stoppedMsg: Message = {
            ...assistantMsg,
            content: contentAccumulator || '[已停止]',
            isStreaming: false
          }
          updateActiveMessages([...messages, userMsg, stoppedMsg])
          return
        }
        throw readError
      }

      setLoading(false)
      setStreamController(null)
    } catch (error) {
      const err = error as any
      if (err.name === 'AbortError' || controller.signal.aborted) {
        return
      }
      message.error(`回复失败: ${err.message}`)
      setLoading(false)
      setStreamController(null)
    }
  }

  // 停止生成
  const handleStop = () => {
    if (streamController) {
      streamController.abort()
      setStreamController(null)
    }
    setLoading(false)
    // 恢复用户原始输入到输入框
    if (originalInput) {
      setInputText(originalInput)
      setOriginalInput('')
    }
    message.info('已停止生成，您可以修改输入后重新生成')
  }

  // 智能写作 (流式生成)
  const handleGenerate = async () => {
    // 如果正在运行，则停止
    if (loading) {
      handleStop()
      return
    }

    if ((!inputText.trim() && !generationMode) || !projectId) return

    // 选区引用拼装：非 generate/fill 模式时，把选区作为引用块并入 user_input（Cursor 式）
    // generate/fill 模式语义是全量生成/补齐，选区无意义，不拼（守卫）
    const isSelectionMode = generationMode !== 'generate' && generationMode !== 'fill'
    const rawInput = inputText.trim()
    let userInput = rawInput
    if (selectedText && isSelectionMode) {
      const quoted = selectedText.slice(0, 2000)
      const quoteBlock = `\n\n【用户引用的原文】\n<引用块开始>\n${quoted}\n<引用块结束>`
      if (userInput) {
        userInput = userInput + quoteBlock
      } else {
        // 选区有但没输需求 → 补默认指令，避免空请求
        userInput = '请针对我引用的原文进行处理' + quoteBlock
      }
    }

    // 保存用户原始输入（纯输入框文本，停止时恢复用，不含引用块）
    setOriginalInput(rawInput)

    const userMsg: Message = {
      role: 'user',
      content: `[智能写作] ${userInput}`,
      timestamp: Date.now()
    }
    
    let assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    }

    const nextMessages = [...messages, userMsg, assistantMsg]
    updateActiveMessages(nextMessages)
    setInputText('')
    setLoading(true)

    // 创建AbortController用于取消请求
    const controller = new AbortController()
    setStreamController(controller)

    let contentAccumulator = ''
    let thinkingAccumulator = ''
    editorContentRef.current = ''  // Reset editor content for new request

    try {
      // 获取保存的 session_id（优先级：currentSessionIdForSolution > 全局变量 > messages 中最新消息的 sessionId）
      let sessionId = currentSessionIdForSolution || (window as any).__current_session_id || null
      
      // 如果还没有找到 session_id，尝试从 messages 中查找最新的包含 sessionId 的消息
      if (!sessionId && messages.length > 0) {
        for (let i = messages.length - 1; i >= 0; i--) {
          const msg = messages[i] as any
          if (msg.sessionId) {
            sessionId = msg.sessionId
            break
          }
        }
      }
      
      const response = await fetch('http://localhost:8000/api/agent/generate-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_input: userInput,
          user_id: 1,
          project_id: projectId,
          domain: (() => {
            // Read default domain from localStorage for this project
            if (projectId) {
              return localStorage.getItem(`profile_default_${projectId}`) || undefined
            }
            return undefined
          })(),
          session_id: sessionId,  // 传递保存的 session_id，保持会话上下文
          reference_materials: selectedMaterials.length > 0 ? selectedMaterials.map(m => ({
            name: m.name,
            content: m.content,
            type: m.type
          })) : undefined,  // 注入选中的素材
          uploaded_file_content: uploadedFile?.status === 'done' ? uploadedFile.content : undefined,
          uploaded_file_name: uploadedFile?.status === 'done' ? uploadedFile.name : undefined,
          generation_mode: generationMode || undefined,
          chat_history: messages.slice(-10).map((m: any) => ({
            role: m.role,
            content: typeof m.content === 'string' ? m.content.slice(0, 500) : '',
          }))  // 注入最近10条对话历史
        }),
        signal: controller.signal  // 支持取消请求
      })

      if (!response.ok) throw new Error('生成请求失败')

      // 贴入是一次性的：请求成功发出后清掉选区引用标签
      onClearSelectedText?.()

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('无法读取流')

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n\n')
          
          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data: ')) continue
            
            try {
              const dataStr = line.slice(6).trim()
              if (dataStr === '[DONE]') break
              
              const data = JSON.parse(dataStr)
              if (data.type === 'mode') {
                // 接收模式消息
                currentModeRef.current = data.mode
                console.info(`[AI助手] 模式: ${data.mode}`)
              } else if (data.type === 'thinking') {
                // Streaming thinking tokens — accumulate and update UI
                thinkingAccumulator += data.content || ''
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  thinkingContent: thinkingAccumulator,
                  isStreaming: true,
                }
                updateActiveMessages([...messages, userMsg, updatedAssistant])
              } else if (data.type === 'content') {
                // Streaming content tokens — accumulate and update UI
                contentAccumulator += data.content || ''
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  thinkingContent: thinkingAccumulator || undefined,
                  isStreaming: true,
                }
                updateActiveMessages([...messages, userMsg, updatedAssistant])
              } else if (data.type === 'improvement_solutions') {
                // 收到改进方案，显示方案选择界面
                const solutions = Array.isArray(data.solutions) ? data.solutions : []
                const todos = Array.isArray(data.todo_items) ? data.todo_items : []
                const sessionId = data.session_id || null
                
                // 保存状态
                setImprovementSolutions(solutions)
                setCurrentSessionIdForSolution(sessionId)
                
                if (sessionId) {
                  (window as any).__current_session_id = sessionId
                }
                
                // 更新助手消息
                contentAccumulator = solutions.length > 0
                  ? `老师，关于您提到的内容，我想到几个更实际的思路，供您参考：`
                  : '正在为您思考改进思路...'

                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  isStreaming: false,
                  improvementSolutions: solutions,
                  todoItems: todos,
                  sessionId: sessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                return // 暂停，等待用户选择方案
              } else if (data.type === 'current_step' && data.current_step === 'analysis_failed') {
                // 分析失败，清除旧的方案并显示错误
                setImprovementSolutions([])
                setCurrentSessionIdForSolution(null)
                
                const errorMsg = data.error || data.message || '需求分析失败，请重试'
                contentAccumulator = `❌ ${errorMsg}`

                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  isStreaming: false
                }
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                message.error(errorMsg)
                return
              } else if (data.type === 'pending_questions') {
                // 收到询问问题，显示问题文本
                const questions = Array.isArray(data.questions) ? data.questions : []
                const questionsText = questions.map((q: any, idx: number) => 
                  `${idx + 1}. ${q.question || q.text || ''}`
                ).join('\n')
                
                // 更新助手消息
                contentAccumulator = questions.length > 0
                  ? `需要补充以下信息：\n\n${questionsText}\n\n请在下方输入框中输入您的回答。`
                  : '等待用户补充信息...'

                // 保存问题数据到消息中
                const sessionId = data.session_id || null
                if (sessionId) {
                  (window as any).__current_session_id = sessionId
                }

                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  isStreaming: false,
                  pendingQuestions: questions,
                  sessionId: sessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                return // 暂停，等待用户回复
              } else if (data.type === 'plan_options') {
                // 收到计划选项，显示计划选项列表
                const options = Array.isArray(data.plan_options) ? data.plan_options : []
                const sessionId = data.session_id || null
                
                // 保存状态
                setPlanOptions(options)
                setCurrentSessionIdForPlan(sessionId)
                setSelectedPlanId(null)
                
                // 更新助手消息
                contentAccumulator = options.length > 0
                  ? `已生成 ${options.length} 个写作方案，请选择其中一个：`
                  : '等待生成方案...'

                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  isStreaming: false,
                  planOptions: options,
                  sessionId: sessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                return // 暂停，等待用户选择
              } else if (data.type === 'progress') {
                assistantMsg = { ...assistantMsg, progressText: data.message || '' }
              } else if (data.type === 'result') {
                // Stream finished — only extract editor content, don't overwrite accumulated text
                // Template mode: editor_content may be empty but template_data is present
                const isTemplateResult = data.content_format === 'template' && data.template_data
                if (data.has_editor && (data.editor_content || isTemplateResult)) {
                  editorContentRef.current = data.editor_content || ''

                  // Template-driven result: switch editor to template mode
                  if (isTemplateResult) {
                    const { useCreationStore } = await import('../../stores/creationStore')
                    const store = useCreationStore.getState()
                    store.setEditorTemplateData(data.template_data)
                    // feedback-rules 节点4a: snapshot the original (diff baseline)
                    store.setOriginalTemplateData(structuredDocToSections(data.template_data))
                  }
                } else {
                  editorContentRef.current = ''
                }
              } else if (data.type === 'error') {
                contentAccumulator += `\n[错误] ${data.error}`
              } else if (data.type === 'warning') {
                // Per-chapter row-gap warnings (e.g. G25a rows left empty after retries)
                contentAccumulator += `\n⚠ ${data.message || ''}\n`
              }

              const updatedAssistant: Message = {
                ...assistantMsg,
                content: contentAccumulator,
                isStreaming: data.type !== 'result' && data.type !== 'error',
                progressText: data.type === 'progress' ? (data.message || '') : undefined,
              }
              updateActiveMessages([...messages, userMsg, updatedAssistant])
            } catch (e) {
              console.error('SSE Error:', e)
            }
          }
        }
      } catch (readError) {
        const err = readError as any
        // 如果是取消操作，不显示错误
        if (err.name === 'AbortError' || controller.signal.aborted) {
          // 更新消息状态为已停止
          const stoppedMsg: Message = {
            ...assistantMsg,
            content: contentAccumulator || '[已停止生成]',
            isStreaming: false
          }
          updateActiveMessages([...messages, userMsg, stoppedMsg])
          return
        }
        throw readError
      }

      // 生成完成后，根据是否有编辑器内容决定是否触发预览
      // Only send to editor when AI explicitly produced editor content (---EDITOR--- marker)
      if (editorContentRef.current && onPreviewContent) {
        onPreviewContent(editorContentRef.current)
        message.success('生成完成，请在编辑器中预览并确认')
      }
    } catch (error) {
      const err = error as any
      // 如果是取消操作，不显示错误
      if (err.name === 'AbortError' || controller.signal.aborted) {
        return
      }
      console.error('Generate Error:', error)
      message.error('生成中断')
      const errorMsg: Message = {
        ...assistantMsg,
        content: contentAccumulator + '\n[网络故障，请检查连接]',
        isStreaming: false
      }
      updateActiveMessages([...messages, userMsg, errorMsg])
    } finally {
      setLoading(false)
      setStreamController(null)
      setOriginalInput('')
      // NOTE: Do NOT reset generationMode here.
      // The fill workflow spans multiple SSE rounds (user input → auto-confirm → execution).
      // Resetting here makes the button lose its highlight prematurely,
      // confusing users about whether they're still in fill mode.
      // generationMode resets when user toggles the button off or starts a new session.
    }
  }

  // Handle temp file upload for AI context
  const handleFileUpload = async (file: File) => {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword',
    ]
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(pdf|docx?|doc)$/i)) {
      message.error('仅支持 PDF、Word 文件')
      return
    }

    setUploadedFile({ name: file.name, content: '', charCount: 0, status: 'uploading' })

    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('http://localhost:8000/api/drafts/upload-temp', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: '上传失败' }))
        throw new Error(errData.detail || '上传失败')
      }
      const data = await response.json()
      setUploadedFile({
        name: data.filename,
        content: data.content,
        charCount: data.char_count,
        status: 'done',
      })
      message.success(`解析完成: ${data.char_count} 字`)
    } catch (error) {
      const err = error as Error
      setUploadedFile({ name: file.name, content: '', charCount: 0, status: 'error' })
      message.error(`文件解析失败: ${err.message}`)
    }
    return false // prevent antd Upload from doing default upload
  }

  const handleNewSession = () => {
    if (projectId) {
      createNewSession(projectId)
      setGenerationMode(null)
      message.success('新会话已创建')
    }
  }

  // 插入内容到编辑器
  const handleInsertContent = (content: string) => {
    if (onDirectInsert) {
      onDirectInsert(content)
    } else {
      onInsertToEditor(content)
    }
    message.success('已插入到编辑器')
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: colors.bgSecondary }}>
      {/* 顶部工具栏 - 简化版 */}
      <div style={{ 
        padding: '12px 16px', 
        borderBottom: `1px solid ${colors.borderLight}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <RocketOutlined style={{ color: colors.primary, fontSize: 18 }} />
          <span style={{ fontWeight: 600, color: colors.textPrimary }}>说出想法！</span>
        </div>
        <Space>
          <Button 
            type="text" 
            icon={<HistoryOutlined />} 
            onClick={() => setHistoryVisible(true)}
            style={{ color: colors.textSecondary }}
          />
          <Button 
            type="text" 
            icon={<PlusOutlined />} 
            onClick={handleNewSession}
            style={{ color: colors.textSecondary }}
          />
          {onClose && (
            <Button 
              type="text" 
              icon={<MenuFoldOutlined />} 
              onClick={onClose}
              style={{ color: colors.textSecondary }}
            />
          )}
        </Space>
      </div>

      {/* 消息展示区 */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16, background: colors.bgPrimary }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', marginTop: 60, color: colors.textTertiary }}>
            <RocketOutlined style={{ fontSize: 40, marginBottom: 16, color: colors.primary }} />
            <p style={{ marginBottom: 8 }}>输入工艺需求，AI 将为您生成工艺文件</p>
            <p style={{ fontSize: 12, color: colors.textTertiary }}>
              生成后将在编辑器中预览，确认后正式写入
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              style={{ 
                marginBottom: 16, 
                borderRadius: 12,
                padding: '12px 16px',
                background: msg.role === 'user' ? colors.primaryLight : colors.bgSecondary,
                boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                border: `1px solid ${msg.role === 'user' ? colors.primary + '30' : colors.borderLight}`,
                animation: 'messageIn 0.25s ease-out'
              }}
            >
              {/* 消息头部 */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: colors.textTertiary }}>
                  {msg.role === 'user' ? '你' : '🤖 工艺助手'}
                </span>
                {msg.role === 'assistant' && !msg.isStreaming && (
                  <Space size={4}>
                    <Button type="text" size="small" icon={<CopyOutlined />} aria-label="复制" title="复制" onClick={() => {
                      navigator.clipboard.writeText(msg.content)
                      message.success('已复制')
                    }} style={{ color: colors.textTertiary }} />
                    <Button 
                      type="text" 
                      size="small" 
                      icon={<PlusOutlined />} 
                      onClick={() => handleInsertContent(msg.content)} 
                      style={{ color: colors.primary }}
                      title="插入到编辑器"
                    />
                  </Space>
                )}
              </div>
              {/* Thinking content — show in real-time during streaming, collapsed after done */}
              {msg.thinkingContent && (
                msg.isStreaming ? (
                  // Streaming: show thinking text live
                  <div style={{
                    marginBottom: 8,
                    padding: 8,
                    background: `${colors.primary}08`,
                    borderRadius: 6,
                    borderLeft: `3px solid ${colors.primary}`,
                  }}>
                    <div style={{ fontSize: 12, color: colors.primary, marginBottom: 4, fontWeight: 500 }}>
                      思考中...
                    </div>
                    <div style={{
                      whiteSpace: 'pre-wrap',
                      fontSize: 12,
                      lineHeight: 1.5,
                      color: colors.textTertiary,
                      maxHeight: 120,
                      overflow: 'auto',
                    }}>
                      {msg.thinkingContent}
                    </div>
                  </div>
                ) : (
                  // Finished: collapsed, click to expand
                  <Collapse
                    size="small"
                    style={{ marginBottom: 8, border: 'none', background: 'transparent' }}
                    items={[{
                      key: 'thinking',
                      label: (
                        <span style={{ fontSize: 12, color: colors.primary, cursor: 'pointer' }}>
                          ▸ 查看思考过程
                        </span>
                      ),
                      children: (
                        <div style={{
                          whiteSpace: 'pre-wrap',
                          fontSize: 12,
                          lineHeight: 1.6,
                          color: colors.textTertiary,
                          maxHeight: 200,
                          overflow: 'auto',
                          background: colors.bgPrimary,
                          padding: 8,
                          borderRadius: 6,
                        }}>
                          {msg.thinkingContent}
                        </div>
                      ),
                    }]}
                  />
                )
              )}
              {/* Streaming progress — show text instead of spinner */}
              {msg.isStreaming && !msg.content && !msg.thinkingContent && (
                <div style={{ padding: '8px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Spin size="small" />
                  <span style={{ color: colors.textTertiary, fontSize: 13 }}>
                    {msg.progressText || '思考中...'}
                  </span>
                </div>
              )}
              {/* Message content with general-knowledge disclaimer split */}
              {(() => {
                const disclaimerPrefix = '本地知识库暂无相关内容，以下基于通识知识简答'
                if (msg.content.startsWith(disclaimerPrefix)) {
                  const rest = msg.content.slice(disclaimerPrefix.length).replace(/^[：:，,]\s*/, '')
                  return (
                    <>
                      {/* Prominent disclaimer banner */}
                      <div style={{
                        marginBottom: 10,
                        padding: '8px 12px',
                        background: '#fff7e6',
                        border: '1px solid #ffd591',
                        borderRadius: 6,
                        fontSize: 12,
                        color: '#ad6800',
                        lineHeight: 1.6,
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 6,
                      }}>
                        <span style={{ flexShrink: 0 }}>⚠️</span>
                        <span>本地知识库暂无相关内容，以下回答基于通识知识，建议上传相关工艺文档获取更准确的指导。</span>
                      </div>
                      {/* Actual answer */}
                      <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8, color: colors.textPrimary }}>
                        {rest}
                      </div>
                    </>
                  )
                }
                return (
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8, color: colors.textPrimary }}>
                    {msg.content}
                  </div>
                )
              })()}
              {/* 如果有待办事项，显示在消息气泡内（只显示标题） */}
              {(msg as any).todoItems && Array.isArray((msg as any).todoItems) && (msg as any).todoItems.length > 0 && (
                <div style={{ marginTop: 12, padding: '12px', background: colors.bgPrimary, borderRadius: 6, border: `1px solid ${colors.borderLight}` }}>
                  <Text strong style={{ fontSize: 13, color: colors.textPrimary, marginBottom: 8, display: 'block' }}>
                    待办事项 {(msg as any).todoItems.filter((t: any) => t.status === 'completed').length}/{(msg as any).todoItems.length}
                  </Text>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {(msg as any).todoItems.map((todo: any) => (
                      <div
                        key={todo.id}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '4px 8px',
                          borderRadius: 4,
                          background: todo.status === 'completed' ? '#f6ffed' : '#fff',
                          border: `1px solid ${todo.status === 'completed' ? '#b7eb8f' : colors.borderLight}`,
                          cursor: 'pointer',
                          fontSize: 12,
                          textDecoration: todo.status === 'completed' ? 'line-through' : 'none',
                          color: todo.status === 'completed' ? colors.textSecondary : colors.textPrimary
                        }}
                        onClick={async () => {
                          if (todo.status === 'completed') return
                          const sessionId = (msg as any).sessionId
                          if (!sessionId) return
                          
                          try {
                            const response = await fetch(`http://localhost:8000/api/agent/todos/${sessionId}/${todo.id}/complete`, {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' }
                            })
                            if (response.ok) {
                              // 更新本地状态
                              const updatedTodos = (msg as any).todoItems.map((t: any) => 
                                t.id === todo.id ? { ...t, status: 'completed' } : t
                              )
                              const updatedMsg = { ...msg, todoItems: updatedTodos } as any
                              const updatedMessages = messages.map((m, i) => i === idx ? updatedMsg : m)
                              updateActiveMessages(updatedMessages)
                            }
                          } catch (error) {
                            console.error('标记待办完成失败:', error)
                          }
                        }}
                      >
                        {todo.status === 'completed' ? '✓ ' : ''}
                        {todo.title}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 如果有改进方案，显示方案选择界面 */}
              {(msg as any).improvementSolutions && Array.isArray((msg as any).improvementSolutions) && (msg as any).improvementSolutions.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <SolutionList
                    solutions={(msg as any).improvementSolutions}
                    sessionId={(msg as any).sessionId}
                    allowMultiple={true}
                    onConfirm={async (selectedIds) => {
                      // 调用API选择方案并继续工作流
                      const sessionId = (msg as any).sessionId
                      if (!sessionId) return

                      try {
                        const response = await fetch('http://localhost:8000/api/agent/select-solution', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            session_id: sessionId,
                            solution_ids: selectedIds
                          })
                        })

                        if (!response.ok) throw new Error('选择方案失败')

                        // 继续流式响应处理
                        const reader = response.body?.getReader()
                        const decoder = new TextDecoder()
                        if (!reader) throw new Error('无法读取流')

                        setLoading(true)
                        let continueContent = ''
                        let continueAssistant: Message = {
                          role: 'assistant',
                          content: '',
                          timestamp: Date.now(),
                          isStreaming: true,
                        }

                        while (true) {
                          const { done, value } = await reader.read()
                          if (done) break

                          const chunk = decoder.decode(value, { stream: true })
                          const lines = chunk.split('\n\n')

                          for (const line of lines) {
                            if (!line.trim() || !line.startsWith('data: ')) continue

                            try {
                              const dataStr = line.slice(6).trim()
                              if (dataStr === '[DONE]') break

                              const continueData = JSON.parse(dataStr)
                              if (continueData.type === 'mode') {
                                currentModeRef.current = continueData.mode
                                console.info(`[AI助手-继续] 模式: ${continueData.mode}`)
                              } else if (continueData.type === 'progress') {
                                continueAssistant = { ...continueAssistant, progressText: continueData.message || '' }
                              } else if (continueData.type === 'result') {
                                continueContent = continueData.content
                              }

                              const updatedMsg: Message = {
                                ...continueAssistant,
                                content: continueContent,
                                isStreaming: continueData.type !== 'result',
                                progressText: continueData.type === 'progress' ? (continueData.message || '') : undefined,
                              }
                              const currentMsgs = messages
                              updateActiveMessages([...currentMsgs, updatedMsg])
                            } catch (e) {
                              console.error('Continue SSE Error:', e)
                            }
                          }
                        }
                        
                        setLoading(false)
                        // 只有写作模式才触发预览，问答模式直接显示结果
                        if (continueContent && onPreviewContent && currentModeRef.current === 'write') {
                          onPreviewContent(continueContent)
                          message.success('生成完成，请在编辑器中预览并确认')
                        }
                      } catch (error) {
                        const err = error as any
                        message.error(`选择方案失败: ${err.message}`)
                        setLoading(false)
                      }
                    }}
                  />
                </div>
              )}
              {/* 如果有计划选项，显示计划选项列表 */}
              {(msg as any).planOptions && Array.isArray((msg as any).planOptions) && (msg as any).planOptions.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <Space direction="vertical" style={{ width: '100%' }} size={12}>
                    {(msg as any).planOptions.map((option: PlanOption) => (
                      <PlanOptionCard
                        key={option.id}
                        option={option}
                        selected={selectedPlanId === option.id}
                        onSelect={() => {
                          setSelectedPlanId(option.id)
                          handleSelectPlan(option.id, (msg as any).sessionId)
                        }}
                      />
                    ))}
                  </Space>
                </div>
              )}
            </div>
          ))
        )}
        {/* Agent协作视图 */}
        {agentCalls.length > 0 && (
          <AgentCollaborationView 
            agentCalls={agentCalls}
            collaborationHistory={collaborationHistory}
          />
        )}
        <div ref={messagesEndRef} />
        <style>{`
          @keyframes messageIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>

        {/* 输入区域 - 简化版只有写作输入 */}
        <div style={{ padding: 16, borderTop: `1px solid ${colors.borderLight}`, background: colors.bgSecondary }}>
        {/* File upload area */}
        {!uploadedFile ? (
          <Upload
            beforeUpload={(file) => { handleFileUpload(file); return false }}
            showUploadList={false}
            accept=".pdf,.docx,.doc"
          >
            <div style={{
              border: `1px dashed ${colors.borderLight}`,
              borderRadius: 8,
              padding: '8px 12px',
              marginBottom: 8,
              textAlign: 'center',
              cursor: 'pointer',
              color: colors.textTertiary,
              fontSize: 12,
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = colors.primary }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = colors.borderLight }}
            >
              <PaperClipOutlined style={{ marginRight: 6 }} />
              点击上传文件作为 AI 上下文（PDF、Word）
            </div>
          </Upload>
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 10px',
            marginBottom: 8,
            borderRadius: 8,
            background: uploadedFile.status === 'error' ? '#fff2f0' : colors.bgPrimary,
            border: `1px solid ${uploadedFile.status === 'error' ? '#ffccc7' : colors.borderLight}`,
            fontSize: 12,
          }}>
            {uploadedFile.status === 'uploading' ? (
              <Spin size="small" />
            ) : uploadedFile.status === 'done' ? (
              <FileTextOutlined style={{ color: colors.primary }} />
            ) : (
              <span style={{ color: '#ff4d4f' }}>!</span>
            )}
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: colors.textPrimary }}>
              {uploadedFile.name}
            </span>
            {uploadedFile.status === 'done' && (
              <span style={{ color: colors.primary, fontSize: 11 }}>
                {uploadedFile.charCount.toLocaleString()} 字
              </span>
            )}
            {uploadedFile.status === 'uploading' && <span style={{ color: colors.textTertiary }}>解析中...</span>}
            {uploadedFile.status === 'error' && <span style={{ color: '#ff4d4f' }}>失败</span>}
            <Button
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={() => setUploadedFile(null)}
              style={{ color: colors.textTertiary, minWidth: 20, padding: 0 }}
            />
          </div>
        )}
        {/* Mode buttons row — single Fill button (merged: fill-with-no-draft
            auto-falls-back to full generation on the backend, so one entry suffices) */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <Button
            size="small"
            className={generationMode === 'fill' ? 'mode-btn-active' : undefined}
            onClick={() => {
              if (workingAreaEmpty) {
                setGateModalOpen(true)
                return
              }
              setGenerationMode(generationMode === 'fill' ? null : 'fill')
            }}
            disabled={loading}
            style={{
              flex: 1,
              borderRadius: 8,
              color: generationMode === 'fill' ? undefined : colors.textSecondary,
              borderColor: generationMode === 'fill' ? undefined : colors.border,
              fontSize: 12,
              fontWeight: generationMode === 'fill' ? 600 : 400,
            }}
          >
            补齐
          </Button>
        </div>
        {/* 选区引用标签（Cursor 式）— selectedText 非空时显示，× 可清除 */}
        {selectedText && (
          <div style={{ marginBottom: 8 }}>
            <Tag
              closable
              onClose={(e) => {
                e?.preventDefault?.()
                onClearSelectedText?.()
              }}
              style={{
                maxWidth: '100%',
                padding: '4px 8px',
                fontSize: 12,
                lineHeight: 1.5,
                whiteSpace: 'normal',
                background: '#e6f7ff',
                borderColor: '#91d5ff',
                color: '#1890ff',
              }}
            >
              📎 引用原文({selectedText.length}字): {selectedText.slice(0, 40)}{selectedText.length > 40 ? '...' : ''}
            </Tag>
          </div>
        )}
        {/* Input + Send row — locked when the working area is empty (N6 gate:
            no silent full-knowledge retrieval; click explains and points to materials).
            readOnly (not disabled) so the click still lands and opens the modal. */}
        <Space.Compact
          style={{ width: '100%', ...(workingAreaEmpty ? { opacity: 0.6, cursor: 'pointer' } : {}) }}
        >
          <TextArea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            placeholder={
              workingAreaEmpty
                ? '请先在素材库勾选素材，再输入工艺需求...'
                : generationMode === 'fill'
                  ? '补齐模式：自动检测并补充缺失章节（空文档将完整生成）...'
                  : '描述你的工艺文件需求，例如：编写一份电缆装配工艺规程...'
            }
            autoSize={{ minRows: 3, maxRows: 6 }}
            readOnly={workingAreaEmpty}
            onClick={() => workingAreaEmpty && setGateModalOpen(true)}
            onPressEnter={e => {
              if (e.ctrlKey || e.metaKey) {
                if (workingAreaEmpty) {
                  setGateModalOpen(true)
                  return
                }
                handleGenerate()
              }
            }}
            style={{ borderRadius: '12px 0 0 12px', ...(workingAreaEmpty ? { cursor: 'pointer' } : {}) }}
          />
          <Button
            type="primary"
            loading={loading && !streamController}
            onClick={() => {
              if (workingAreaEmpty) {
                setGateModalOpen(true)
                return
              }
              handleGenerate()
            }}
            disabled={workingAreaEmpty || (!inputText.trim() && !generationMode && !loading) || !projectId}
            danger={loading}
            style={{
              height: 'auto',
              background: loading ? '#ff4d4f' : colors.primary,
              borderColor: loading ? '#ff4d4f' : colors.primary,
              borderRadius: '0 12px 12px 0'
            }}
            icon={loading ? <StopOutlined /> : <RocketOutlined />}
          >
            {loading ? '停止' : '发送'}
          </Button>
        </Space.Compact>
        <div style={{ marginTop: 8, fontSize: 11, color: colors.textTertiary }}>
          按 Ctrl+Enter 快捷发送
        </div>
      </div>

      {/* N6 gate modal: empty working area → must pick materials first */}
      <Modal
        open={gateModalOpen}
        onCancel={() => setGateModalOpen(false)}
        title="请先勾选素材"
        footer={[
          <Button key="cancel" onClick={() => setGateModalOpen(false)}>
            稍后再说
          </Button>,
          <Button
            key="go"
            type="primary"
            onClick={() => {
              setGateModalOpen(false)
              onOpenMaterials?.()
            }}
          >
            去素材库勾选
          </Button>,
        ]}
      >
        <p style={{ margin: 0, lineHeight: 1.8 }}>
          当前项目的工作区域还没有勾选任何素材。为避免检索范围不清、生成内容来源不明，
          请先在左侧素材库勾选本次工作要用的素材（可单个勾选或整组勾选），勾选完成后即可输入需求生成。
        </p>
      </Modal>

      {/* 历史记录抽屉 */}
      <Drawer
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <HistoryOutlined style={{ color: colors.primary }} />
            会话历史
          </span>
        }
        onClose={() => setHistoryVisible(false)}
        open={historyVisible}
        width={280}
        styles={{ body: { padding: 12, background: colors.bgPrimary } }}
      >
        <List
          dataSource={sessions}
          renderItem={item => (
            <List.Item
              onClick={() => {
                if (projectId) {
                  switchSession(projectId, item.id)
                  setHistoryVisible(false)
                }
              }}
              style={{ 
                cursor: 'pointer',
                background: item.id === activeSessionId ? colors.primaryLight : colors.bgSecondary,
                borderRadius: 10,
                padding: '10px 12px',
                marginBottom: 8,
                border: item.id === activeSessionId ? `1px solid ${colors.primary}40` : `1px solid ${colors.borderLight}`
              }}
              actions={[
                <Popconfirm
                  title="彻底删除此对话？"
                  onConfirm={e => {
                    e?.stopPropagation()
                    if (projectId) deleteSession(projectId, item.id)
                  }}
                  onCancel={e => e?.stopPropagation()}
                >
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} aria-label="删除" title="删除" onClick={e => e.stopPropagation()} />
                </Popconfirm>
              ]}
            >
              <List.Item.Meta
                avatar={<MessageOutlined style={{ color: colors.primary, marginTop: 4 }} />}
                title={<Text ellipsis={{ tooltip: item.title }} style={{ fontWeight: item.id === activeSessionId ? 600 : 400 }}>{item.title}</Text>}
                description={<Text type="secondary" style={{ fontSize: 11 }}>{new Date(item.timestamp).toLocaleDateString()}</Text>}
              />
            </List.Item>
          )}
        />
      </Drawer>
    </div>
  )
}

export default AIChatPanel
