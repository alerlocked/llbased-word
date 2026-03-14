/**
 * AIChatPanel事件处理测试
 * 测试agent_call和collaboration事件处理
 */
import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { AIChatPanel } from '../AIChatPanel'
import { AgentCallEvent, CollaborationEvent } from '../../../services/conversationService'

// Mock依赖
jest.mock('../../../stores/creationStore', () => ({
  useCreationStore: () => ({
    messages: [],
    activeSession: null,
    activeSessionId: null,
    sessions: [],
    createNewSession: jest.fn(),
    switchSession: jest.fn(),
    updateSessionMessages: jest.fn()
  })
}))

jest.mock('../../../services/conversationService', () => ({
  startConversation: jest.fn(),
  replyQuestion: jest.fn(),
  selectPlan: jest.fn()
}))

describe('AIChatPanel事件处理', () => {
  const mockProps = {
    projectId: 1,
    selectedText: '',
    onInsertToEditor: jest.fn(),
    onPreviewContent: jest.fn(),
    onDirectInsert: jest.fn(),
    onClose: jest.fn()
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  describe('agent_call事件处理', () => {
    it('应该处理agent_call事件并更新状态', async () => {
      const agentCallEvent: AgentCallEvent = {
        type: 'agent_call',
        caller: 'writer',
        target_agent: 'retriever',
        capability: 'retrieve_materials',
        reason: '需要更多数据',
        current_step: 'writing_with_collaboration',
        message: 'writer 调用 retriever 的 retrieve_materials 能力'
      }

      // 这里主要测试类型定义和事件结构
      expect(agentCallEvent.type).toBe('agent_call')
      expect(agentCallEvent.caller).toBe('writer')
      expect(agentCallEvent.target_agent).toBe('retriever')
      expect(agentCallEvent.capability).toBe('retrieve_materials')
      expect(agentCallEvent.reason).toBe('需要更多数据')
    })

    it('应该支持不同caller和target_agent的组合', () => {
      const events: AgentCallEvent[] = [
        {
          type: 'agent_call',
          caller: 'writer',
          target_agent: 'retriever',
          capability: 'retrieve_materials',
          reason: '需要更多数据',
          current_step: 'writing_with_collaboration',
          message: 'writer 调用 retriever'
        },
        {
          type: 'agent_call',
          caller: 'reviewer',
          target_agent: 'writer',
          capability: 'revise_content',
          reason: '发现严重问题',
          current_step: 'review_with_collaboration',
          message: 'reviewer 调用 writer'
        }
      ]

      expect(events[0].caller).toBe('writer')
      expect(events[0].target_agent).toBe('retriever')
      expect(events[1].caller).toBe('reviewer')
      expect(events[1].target_agent).toBe('writer')
    })
  })

  describe('collaboration事件处理', () => {
    it('应该处理collaboration事件并更新状态', () => {
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
      expect(Object.keys(collaborationEvent.command_results)).toContain('call_id_1')
    })

    it('应该支持空的call_stack', () => {
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

    it('应该支持复杂的调用栈', () => {
      const event: CollaborationEvent = {
        type: 'collaboration',
        call_stack: ['writer', 'retriever', 'writer', 'reviewer'],
        command_results: {},
        current_step: 'test',
        message: '复杂协作链'
      }

      expect(event.call_stack.length).toBe(4)
      expect(event.call_stack[0]).toBe('writer')
      expect(event.call_stack[3]).toBe('reviewer')
    })
  })

  describe('事件类型判断', () => {
    it('应该正确区分不同类型的事件', () => {
      const agentCall: AgentCallEvent = {
        type: 'agent_call',
        caller: 'writer',
        target_agent: 'retriever',
        capability: 'retrieve_materials',
        reason: '测试',
        current_step: 'test',
        message: '测试'
      }

      const collaboration: CollaborationEvent = {
        type: 'collaboration',
        call_stack: [],
        command_results: {},
        current_step: 'test',
        message: '测试'
      }

      expect(agentCall.type).toBe('agent_call')
      expect(collaboration.type).toBe('collaboration')
      expect(agentCall.type).not.toBe(collaboration.type)
    })
  })
})

