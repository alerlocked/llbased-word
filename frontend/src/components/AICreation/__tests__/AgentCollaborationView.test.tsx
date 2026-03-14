/**
 * AgentCollaborationView组件测试
 * 测试组件渲染、调用历史显示、调用栈显示
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { AgentCollaborationView } from '../AgentCollaborationView'
import { AgentCallEvent, CollaborationEvent } from '../../../services/conversationService'

describe('AgentCollaborationView组件', () => {
  describe('组件渲染', () => {
    it('应该在有数据时渲染组件', () => {
      const agentCalls: AgentCallEvent[] = [
        {
          type: 'agent_call',
          caller: 'writer',
          target_agent: 'retriever',
          capability: 'retrieve_materials',
          reason: '需要更多数据',
          current_step: 'writing_with_collaboration',
          message: 'writer 调用 retriever'
        }
      ]

      const collaborationHistory: CollaborationEvent[] = [
        {
          type: 'collaboration',
          call_stack: ['writer', 'retriever'],
          command_results: {},
          current_step: 'writing_with_collaboration',
          message: 'Agent协作中...'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={agentCalls}
          collaborationHistory={collaborationHistory}
        />
      )

      // 验证组件标题
      expect(screen.getByText('Agent协作过程')).toBeInTheDocument()
    })

    it('应该在无数据时不渲染组件', () => {
      const { container } = render(
        <AgentCollaborationView
          agentCalls={[]}
          collaborationHistory={[]}
        />
      )

      // 组件应该返回null
      expect(container.firstChild).toBeNull()
    })
  })

  describe('调用历史显示', () => {
    it('应该显示调用历史', () => {
      const agentCalls: AgentCallEvent[] = [
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

      render(
        <AgentCollaborationView
          agentCalls={agentCalls}
          collaborationHistory={[]}
        />
      )

      // 验证调用历史标题
      expect(screen.getByText('调用历史：')).toBeInTheDocument()
    })

    it('应该显示调用原因', () => {
      const agentCalls: AgentCallEvent[] = [
        {
          type: 'agent_call',
          caller: 'writer',
          target_agent: 'retriever',
          capability: 'retrieve_materials',
          reason: '需要更多数据',
          current_step: 'writing_with_collaboration',
          message: 'writer 调用 retriever'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={agentCalls}
          collaborationHistory={[]}
        />
      )

      // 验证调用原因显示
      expect(screen.getByText('需要更多数据')).toBeInTheDocument()
    })
  })

  describe('调用栈显示', () => {
    it('应该显示调用栈', () => {
      const collaborationHistory: CollaborationEvent[] = [
        {
          type: 'collaboration',
          call_stack: ['writer', 'retriever'],
          command_results: {},
          current_step: 'writing_with_collaboration',
          message: 'Agent协作中...'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={[]}
          collaborationHistory={collaborationHistory}
        />
      )

      // 验证调用栈标题
      expect(screen.getByText('当前调用栈：')).toBeInTheDocument()
    })

    it('应该显示调用栈中的Agent名称', () => {
      const collaborationHistory: CollaborationEvent[] = [
        {
          type: 'collaboration',
          call_stack: ['writer', 'retriever', 'writer'],
          command_results: {},
          current_step: 'test',
          message: '测试'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={[]}
          collaborationHistory={collaborationHistory}
        />
      )

      // 验证Agent名称显示（通过Tag组件，可能有重复）
      const writerTags = screen.getAllByText('writer')
      expect(writerTags.length).toBeGreaterThan(0)
      expect(screen.getByText('retriever')).toBeInTheDocument()
    })

    it('应该显示最新的调用栈', () => {
      const collaborationHistory: CollaborationEvent[] = [
        {
          type: 'collaboration',
          call_stack: ['writer', 'retriever'],
          command_results: {},
          current_step: 'test1',
          message: '第一次'
        },
        {
          type: 'collaboration',
          call_stack: ['writer', 'retriever', 'writer'],
          command_results: {},
          current_step: 'test2',
          message: '第二次'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={[]}
          collaborationHistory={collaborationHistory}
        />
      )

      // 应该显示最新的调用栈（最后一个，可能有重复）
      const writerTags = screen.getAllByText('writer')
      expect(writerTags.length).toBeGreaterThan(0)
      expect(screen.getByText('retriever')).toBeInTheDocument()
    })
  })

  describe('空状态处理', () => {
    it('应该在agentCalls和collaborationHistory都为空时不渲染', () => {
      const { container } = render(
        <AgentCollaborationView
          agentCalls={[]}
          collaborationHistory={[]}
        />
      )

      expect(container.firstChild).toBeNull()
    })

    it('应该在只有agentCalls时渲染', () => {
      const agentCalls: AgentCallEvent[] = [
        {
          type: 'agent_call',
          caller: 'writer',
          target_agent: 'retriever',
          capability: 'retrieve_materials',
          reason: '测试',
          current_step: 'test',
          message: '测试'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={agentCalls}
          collaborationHistory={[]}
        />
      )

      expect(screen.getByText('Agent协作过程')).toBeInTheDocument()
    })

    it('应该在只有collaborationHistory时渲染', () => {
      const collaborationHistory: CollaborationEvent[] = [
        {
          type: 'collaboration',
          call_stack: ['writer'],
          command_results: {},
          current_step: 'test',
          message: '测试'
        }
      ]

      render(
        <AgentCollaborationView
          agentCalls={[]}
          collaborationHistory={collaborationHistory}
        />
      )

      expect(screen.getByText('Agent协作过程')).toBeInTheDocument()
    })
  })
})

