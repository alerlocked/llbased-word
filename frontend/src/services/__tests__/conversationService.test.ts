/**
 * conversationService类型测试
 * 验证AgentCallEvent、CollaborationEvent和SSEEvent类型定义
 */
import { AgentCallEvent, CollaborationEvent, SSEEvent } from '../conversationService'

describe('conversationService类型定义', () => {
  describe('AgentCallEvent', () => {
    it('应该正确定义AgentCallEvent类型', () => {
      const agentCallEvent: AgentCallEvent = {
        type: 'agent_call',
        caller: 'writer',
        target_agent: 'retriever',
        capability: 'retrieve_materials',
        reason: '需要更多数据',
        current_step: 'writing_with_collaboration',
        message: 'writer 调用 retriever 的 retrieve_materials 能力'
      }

      expect(agentCallEvent.type).toBe('agent_call')
      expect(agentCallEvent.caller).toBe('writer')
      expect(agentCallEvent.target_agent).toBe('retriever')
      expect(agentCallEvent.capability).toBe('retrieve_materials')
      expect(agentCallEvent.reason).toBe('需要更多数据')
      expect(agentCallEvent.current_step).toBe('writing_with_collaboration')
      expect(agentCallEvent.message).toBe('writer 调用 retriever 的 retrieve_materials 能力')
    })

    it('应该包含所有必需字段', () => {
      const event: AgentCallEvent = {
        type: 'agent_call',
        caller: 'reviewer',
        target_agent: 'writer',
        capability: 'revise_content',
        reason: '发现严重问题',
        current_step: 'review_with_collaboration',
        message: 'reviewer 调用 writer 的 revise_content 能力'
      }

      expect(event).toHaveProperty('type')
      expect(event).toHaveProperty('caller')
      expect(event).toHaveProperty('target_agent')
      expect(event).toHaveProperty('capability')
      expect(event).toHaveProperty('reason')
      expect(event).toHaveProperty('current_step')
      expect(event).toHaveProperty('message')
    })
  })

  describe('CollaborationEvent', () => {
    it('应该正确定义CollaborationEvent类型', () => {
      const collaborationEvent: CollaborationEvent = {
        type: 'collaboration',
        call_stack: ['writer', 'retriever'],
        command_results: {
          'call_id_1': {
            caller: 'writer',
            target: 'retriever',
            capability: 'retrieve_materials',
            success: true,
            result: { materials: {} }
          }
        },
        current_step: 'writing_with_collaboration',
        message: 'Agent协作中...'
      }

      expect(collaborationEvent.type).toBe('collaboration')
      expect(collaborationEvent.call_stack).toEqual(['writer', 'retriever'])
      expect(collaborationEvent.command_results).toBeDefined()
      expect(collaborationEvent.current_step).toBe('writing_with_collaboration')
      expect(collaborationEvent.message).toBe('Agent协作中...')
    })

    it('应该支持空的call_stack和command_results', () => {
      const event: CollaborationEvent = {
        type: 'collaboration',
        call_stack: [],
        command_results: {},
        current_step: 'test',
        message: '测试'
      }

      expect(event.call_stack).toEqual([])
      expect(event.command_results).toEqual({})
    })
  })

  describe('SSEEvent联合类型', () => {
    it('应该支持agent_call事件', () => {
      const event: SSEEvent = {
        type: 'agent_call',
        caller: 'writer',
        target_agent: 'retriever',
        capability: 'retrieve_materials',
        reason: '需要更多数据',
        current_step: 'writing_with_collaboration',
        message: 'writer 调用 retriever'
      }

      expect(event.type).toBe('agent_call')
      if (event.type === 'agent_call') {
        expect(event.caller).toBe('writer')
        expect(event.target_agent).toBe('retriever')
      }
    })

    it('应该支持collaboration事件', () => {
      const event: SSEEvent = {
        type: 'collaboration',
        call_stack: ['writer', 'retriever'],
        command_results: {},
        current_step: 'writing_with_collaboration',
        message: 'Agent协作中...'
      }

      expect(event.type).toBe('collaboration')
      if (event.type === 'collaboration') {
        expect(event.call_stack).toEqual(['writer', 'retriever'])
      }
    })

    it('应该支持progress事件', () => {
      const event: SSEEvent = {
        type: 'progress',
        node: 'writer',
        current_step: 'writing',
        message: '正在撰写...',
        data: {
          content_preview: '测试内容'
        }
      }

      expect(event.type).toBe('progress')
      if (event.type === 'progress') {
        expect(event.node).toBe('writer')
        expect(event.data).toBeDefined()
      }
    })

    it('应该支持plan_options事件', () => {
      const event: SSEEvent = {
        type: 'plan_options',
        session_id: 'test_session',
        plan_options: [],
        current_step: 'planning',
        message: '请选择写作方案'
      }

      expect(event.type).toBe('plan_options')
      if (event.type === 'plan_options') {
        expect(event.session_id).toBe('test_session')
        expect(event.plan_options).toEqual([])
      }
    })

    it('应该支持pending_questions事件', () => {
      const event: SSEEvent = {
        type: 'pending_questions',
        session_id: 'test_session',
        questions: [],
        current_step: 'analyzing',
        message: '需要补充信息'
      }

      expect(event.type).toBe('pending_questions')
      if (event.type === 'pending_questions') {
        expect(event.session_id).toBe('test_session')
        expect(event.questions).toEqual([])
      }
    })

    it('应该支持result事件', () => {
      const event: SSEEvent = {
        type: 'result',
        status: 'success',
        content: '测试内容',
        review: {}
      }

      expect(event.type).toBe('result')
      if (event.type === 'result') {
        expect(event.status).toBe('success')
        expect(event.content).toBe('测试内容')
      }
    })

    it('应该支持error事件', () => {
      const event: SSEEvent = {
        type: 'error',
        error: '测试错误'
      }

      expect(event.type).toBe('error')
      if (event.type === 'error') {
        expect(event.error).toBe('测试错误')
      }
    })
  })
})

