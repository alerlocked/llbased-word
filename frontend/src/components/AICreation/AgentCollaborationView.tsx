/**
 * Agent协作可视化组件
 * 显示Agent调用关系图和调用栈
 */
import React from 'react'
import { Card, Tag } from 'antd'
import { AgentCallEvent, CollaborationEvent } from '../../services/conversationService'

interface AgentCollaborationViewProps {
  agentCalls: AgentCallEvent[]
  collaborationHistory: CollaborationEvent[]
}

export const AgentCollaborationView: React.FC<AgentCollaborationViewProps> = ({
  agentCalls,
  collaborationHistory
}) => {
  if (agentCalls.length === 0 && collaborationHistory.length === 0) {
    return null
  }

  return (
    <Card 
      title="Agent协作过程" 
      size="small" 
      style={{ marginTop: 16 }}
    >
      {agentCalls.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 'bold', marginBottom: 8 }}>调用历史：</div>
          <div>
            {agentCalls.map((call, index) => (
              <div key={index} style={{ marginBottom: 8, paddingLeft: 16, borderLeft: '2px solid #1890ff' }}>
                <div>
                  <Tag color="blue">{call.caller}</Tag>
                  <span> → </span>
                  <Tag color="green">{call.target_agent}</Tag>
                  <div style={{ marginTop: 4, fontSize: 12, color: '#666' }}>
                    {call.reason}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {collaborationHistory.length > 0 && (
        <div>
          <div style={{ fontWeight: 'bold', marginBottom: 8 }}>当前调用栈：</div>
          {collaborationHistory[collaborationHistory.length - 1].call_stack.map((agent, index) => (
            <Tag key={index} style={{ marginRight: 4 }}>
              {agent}
            </Tag>
          ))}
        </div>
      )}
    </Card>
  )
}

