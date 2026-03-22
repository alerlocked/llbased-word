/**
 * AIChatPanel - AI交互面板
 * 上方：对话历史 | 下方：输入框和快捷操作
 * 温暖黄色系视觉风格
 */
import { useState, useEffect, useRef } from 'react'
import { Input, Button, Space, message, Spin, Drawer, List, Typography, Popconfirm } from 'antd'
import { CopyOutlined, PlusOutlined, RocketOutlined, HistoryOutlined, DeleteOutlined, MenuFoldOutlined, MessageOutlined, StopOutlined } from '@ant-design/icons'
import { useCreationStore, Message } from '../../stores/creationStore'
import { colors } from '../../styles/design-tokens'
import { PlanOptionCard } from './PlanOptionCard'
import { AgentCollaborationView } from './AgentCollaborationView'
import { PlanOption, AgentCallEvent, CollaborationEvent } from '../../services/conversationService'
import { SolutionList, ImprovementSolution } from './SolutionList'

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
}

const AIChatPanel: React.FC<AIChatPanelProps> = ({ 
  projectId, 
  selectedText,
  onInsertToEditor,
  onDirectInsert,
  onPreviewContent,
  onClose
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
  const [historyVisible, setHistoryVisible] = useState(false)
  // 流式读取控制器，用于停止生成
  const [streamController, setStreamController] = useState<AbortController | null>(null)
  // 保存用户原始输入，用于停止时恢复
  const [originalInput, setOriginalInput] = useState<string>('')
  // 当前模式（qa 或 write）- 使用 useRef 避免异步更新问题
  const currentModeRef = useRef<'qa' | 'write'>('write')
  
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

  // 当选中文本变化时，可以作为写作参考
  useEffect(() => {
    if (selectedText && !inputText) {
      // 可以将选中文本作为写作主题参考
    }
  }, [selectedText])

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
    
    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
      steps: [
        { title: '任务规划', status: 'finish' },
        { title: '素材检索', status: 'wait' },
        { title: '内容撰写', status: 'wait' },
        { title: '质量评审', status: 'wait' }
      ]
    }

    const nextMessages = [...messages, userMsg, assistantMsg]
    updateActiveMessages(nextMessages)
    setLoading(true)

    let contentAccumulator = ''
    let stepsAccumulator = [...assistantMsg.steps!]

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
                stepsAccumulator[0].status = 'finish'
                
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  steps: [...stepsAccumulator],
                  isStreaming: false,
                  planOptions: options,
                  sessionId: data.session_id || sessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                setStreamController(null)
                return
              } else if (data.type === 'agent_call') {
                // 记录Agent调用
                const agentCallData = data as AgentCallEvent
                setAgentCalls(prev => [...prev, agentCallData])
                
                // 更新步骤描述，显示协作信息
                const callMessage = `${agentCallData.caller} → ${agentCallData.target_agent}: ${agentCallData.reason}`
                
                // 根据调用的Agent更新对应步骤
                if (agentCallData.target_agent === 'retriever') {
                  stepsAccumulator[1].status = 'process'
                  stepsAccumulator[1].description = `协作中: ${agentCallData.reason}`
                } else if (agentCallData.target_agent === 'writer') {
                  stepsAccumulator[2].status = 'process'
                  stepsAccumulator[2].description = `协作中: ${agentCallData.reason}`
                }
                
                // 添加到消息内容
                contentAccumulator += `\n\n[协作] ${callMessage}`
              } else if (data.type === 'collaboration') {
                // 记录协作过程
                const collaborationData = data as CollaborationEvent
                setCollaborationHistory(prev => [...prev, collaborationData])
                
                // 显示调用栈
                if (collaborationData.call_stack.length > 0) {
                  const stackInfo = `调用链: ${collaborationData.call_stack.join(' → ')}`
                  contentAccumulator += `\n\n[协作链] ${stackInfo}`
                }
              } else if (data.type === 'progress') {
                if (data.node === 'retriever') {
                  stepsAccumulator[0].status = 'finish'
                  stepsAccumulator[1].status = 'process'
                  stepsAccumulator[1].description = `找到 ${data.data.materials_count?.local || 0} 条素材`
                } else if (data.node === 'writer') {
                  stepsAccumulator[1].status = 'finish'
                  stepsAccumulator[2].status = 'process'
                  contentAccumulator = data.data.content_preview || contentAccumulator
                } else if (data.node === 'reviewer') {
                  stepsAccumulator[2].status = 'finish'
                  stepsAccumulator[3].status = 'process'
                }
              } else if (data.type === 'result') {
                contentAccumulator = data.content
                stepsAccumulator[3].status = 'finish'
              } else if (data.type === 'error') {
                contentAccumulator += `\n[错误] ${data.error}`
              }
              
              const updatedAssistant: Message = {
                ...assistantMsg,
                content: contentAccumulator,
                steps: [...stepsAccumulator],
                isStreaming: data.type !== 'result' && data.type !== 'error'
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
    
    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
      steps: [
        { title: '任务规划', status: 'wait' },
        { title: '素材检索', status: 'wait' },
        { title: '内容撰写', status: 'wait' },
        { title: '质量评审', status: 'wait' }
      ]
    }

    const nextMessages = [...messages, userMsg, assistantMsg]
    updateActiveMessages(nextMessages)
    setInputText('')
    setLoading(true)

    let contentAccumulator = ''
    let stepsAccumulator = [...assistantMsg.steps!]

    try {
      // 创建AbortController用于取消请求
      const controller = new AbortController()
      setStreamController(controller)

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
                stepsAccumulator[0].status = 'wait'
                stepsAccumulator[0].description = '等待用户补充信息'
                
                const newSessionId = data.session_id || sessionId
                if (newSessionId) {
                  (window as any).__current_session_id = newSessionId
                }
                
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  steps: [...stepsAccumulator],
                  isStreaming: false,
                  pendingQuestions: questions,
                  sessionId: newSessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                setStreamController(null)
                return
              } else if (data.type === 'progress') {
                if (data.node === 'planner') {
                  stepsAccumulator[0].status = 'process'
                  stepsAccumulator[0].description = data.message
                } else if (data.node === 'retriever') {
                  stepsAccumulator[0].status = 'finish'
                  stepsAccumulator[1].status = 'process'
                  stepsAccumulator[1].description = `找到 ${data.data.materials_count?.local || 0} 条素材`
                } else if (data.node === 'writer') {
                  stepsAccumulator[1].status = 'finish'
                  stepsAccumulator[2].status = 'process'
                  contentAccumulator = data.data.content_preview || contentAccumulator
                } else if (data.node === 'reviewer') {
                  stepsAccumulator[2].status = 'finish'
                  stepsAccumulator[3].status = 'process'
                }
              } else if (data.type === 'result') {
                contentAccumulator = data.content
                stepsAccumulator[3].status = 'finish'
              } else if (data.type === 'error') {
                contentAccumulator += `\n[错误] ${data.error}`
              }
              
              const updatedAssistant: Message = {
                ...assistantMsg,
                content: contentAccumulator,
                steps: [...stepsAccumulator],
                isStreaming: data.type !== 'result' && data.type !== 'error'
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

    if (!inputText.trim() || !projectId) return

    // 保存用户原始输入
    const userInput = inputText.trim()
    setOriginalInput(userInput)

    const userMsg: Message = {
      role: 'user',
      content: `[智能写作] ${userInput}`,
      timestamp: Date.now()
    }
    
    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
      steps: [
        { title: '任务规划', status: 'wait' },
        { title: '素材检索', status: 'wait' },
        { title: '内容撰写', status: 'wait' },
        { title: '质量评审', status: 'wait' }
      ]
    }

    const nextMessages = [...messages, userMsg, assistantMsg]
    updateActiveMessages(nextMessages)
    setInputText('')
    setLoading(true)

    // 创建AbortController用于取消请求
    const controller = new AbortController()
    setStreamController(controller)

    let contentAccumulator = ''
    let stepsAccumulator = [...assistantMsg.steps!]

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
          session_id: sessionId  // 传递保存的 session_id，保持会话上下文
        }),
        signal: controller.signal  // 支持取消请求
      })

      if (!response.ok) throw new Error('生成请求失败')

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
                logger.info(`[AI助手] 模式: ${data.mode}`)
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
                
                // 更新助手消息（谦逊、询问的语气）
                contentAccumulator = solutions.length > 0 
                  ? `老师，关于您提到的内容，我想到几个更实际的思路，供您参考：`
                  : '正在为您思考改进思路...'
                stepsAccumulator[0].status = 'wait'
                stepsAccumulator[0].description = '等待您的选择'
                
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  steps: [...stepsAccumulator],
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
                stepsAccumulator[0].status = 'error'
                stepsAccumulator[0].description = '分析失败'
                
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  steps: [...stepsAccumulator],
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
                stepsAccumulator[0].status = 'wait'
                stepsAccumulator[0].description = '等待用户补充信息'
                
                // 保存问题数据到消息中（用于后续回复）
                const sessionId = data.session_id || null
                if (sessionId) {
                  (window as any).__current_session_id = sessionId
                }
                
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  steps: [...stepsAccumulator],
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
                stepsAccumulator[0].status = 'finish'
                stepsAccumulator[0].description = '方案已生成'
                
                const updatedAssistant: Message = {
                  ...assistantMsg,
                  content: contentAccumulator,
                  steps: [...stepsAccumulator],
                  isStreaming: false,
                  planOptions: options,
                  sessionId: sessionId
                } as any
                updateActiveMessages([...messages, userMsg, updatedAssistant])
                setLoading(false)
                return // 暂停，等待用户选择
              } else if (data.type === 'progress') {
                // 处理各种进度消息
                if (data.node === 'context_loader') {
                  // 新增：处理上下文加载进度
                  stepsAccumulator[0].status = 'process'
                  stepsAccumulator[0].description = data.message || '正在加载工艺文档上下文...'
                } else if (data.node === 'planner') {
                  stepsAccumulator[0].status = 'process'
                  stepsAccumulator[0].description = data.message
                } else if (data.node === 'retriever') {
                  stepsAccumulator[0].status = 'finish'
                  stepsAccumulator[1].status = 'process'
                  stepsAccumulator[1].description = `找到 ${data.data?.materials_count?.local || 0} 条素材`
                } else if (data.node === 'writer') {
                  stepsAccumulator[1].status = 'finish'
                  stepsAccumulator[2].status = 'process'
                  contentAccumulator = data.data?.content_preview || contentAccumulator
                } else if (data.node === 'reviewer') {
                  stepsAccumulator[2].status = 'finish'
                  stepsAccumulator[3].status = 'process'
                }
              } else if (data.type === 'result') {
                contentAccumulator = data.content
                stepsAccumulator[3].status = 'finish'
              } else if (data.type === 'error') {
                contentAccumulator += `\n[错误] ${data.error}`
              }
              
              const updatedAssistant: Message = {
                ...assistantMsg,
                content: contentAccumulator,
                steps: [...stepsAccumulator],
                isStreaming: data.type !== 'result' && data.type !== 'error'
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

      // 生成完成后，根据模式决定是否触发预览
      // 只有写作模式才触发预览，问答模式直接显示结果
      if (contentAccumulator && onPreviewContent && currentModeRef.current === 'write') {
        onPreviewContent(contentAccumulator)
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
    }
  }

  const handleNewSession = () => {
    if (projectId) {
      createNewSession(projectId)
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
                  {msg.role === 'user' ? '你' : '🤖 阿西莫夫'}
                </span>
                {msg.role === 'assistant' && !msg.isStreaming && (
                  <Space size={4}>
                    <Button type="text" size="small" icon={<CopyOutlined />} onClick={() => {
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
              {/* 移除步骤框，回答直接显示在原响应框 */}
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8, color: colors.textPrimary }}>
                {msg.content || (msg.isStreaming ? <Spin size="small" /> : '')}
              </div>
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
                        let continueContent = contentAccumulator
                        let continueSteps = [...stepsAccumulator]
                        
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
                              if (continueData.type === 'progress') {
                                if (continueData.node === 'planner') {
                                  continueSteps[0].status = 'process'
                                  continueSteps[0].description = continueData.message
                                } else if (continueData.node === 'retriever') {
                                  continueSteps[0].status = 'finish'
                                  continueSteps[1].status = 'process'
                                } else if (continueData.node === 'writer') {
                                  continueSteps[1].status = 'finish'
                                  continueSteps[2].status = 'process'
                                  continueContent = continueData.data.content_preview || continueContent
                                } else if (continueData.node === 'reviewer') {
                                  continueSteps[2].status = 'finish'
                                  continueSteps[3].status = 'process'
                                }
                              } else if (continueData.type === 'result') {
                                continueContent = continueData.content
                                continueSteps[3].status = 'finish'
                              }
                              
                              const updatedMsg: Message = {
                                ...assistantMsg,
                                content: continueContent,
                                steps: [...continueSteps],
                                isStreaming: continueData.type !== 'result'
                              }
                              updateActiveMessages([...messages, userMsg, updatedMsg])
                            } catch (e) {
                              console.error('Continue SSE Error:', e)
                            }
                          }
                        }
                        
                        setLoading(false)
                        if (continueContent && onPreviewContent) {
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
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            placeholder="输入写作主题，例如：关于人工智能发展历程的深度报道..."
            autoSize={{ minRows: 3, maxRows: 6 }}
            onPressEnter={e => {
              if (e.ctrlKey || e.metaKey) handleGenerate()
            }}
            style={{ borderRadius: '12px 0 0 12px' }}
          />
          <Button 
            type="primary" 
            loading={loading && !streamController} 
            onClick={handleGenerate}
            disabled={(!inputText.trim() && !loading) || !projectId}
            danger={loading}
            style={{ 
              height: 'auto', 
              background: loading ? '#ff4d4f' : colors.primary, 
              borderColor: loading ? '#ff4d4f' : colors.primary,
              borderRadius: '0 12px 12px 0'
            }}
            icon={loading ? <StopOutlined /> : <RocketOutlined />}
          >
            {loading ? '停止' : '生成'}
          </Button>
        </Space.Compact>
        <div style={{ marginTop: 8, fontSize: 11, color: colors.textTertiary }}>
          按 Ctrl+Enter 快捷发送
        </div>
      </div>

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
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={e => e.stopPropagation()} />
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
