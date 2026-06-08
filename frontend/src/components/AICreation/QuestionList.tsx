/**
 * QuestionList - 问题列表组件
 * 显示所有问题，支持点击选择，显示已回答状态
 */
import React from 'react'
import { Card, Space, Typography } from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

const { Text } = Typography

// 确保Question接口导出

export interface Question {
  id: string
  question: string
  question_type?: string
  options?: Array<{ id: string; text: string; description?: string }>
  allow_custom?: boolean
  required?: boolean
}

interface QuestionListProps {
  /** 问题列表 */
  questions: Question[]
  /** 已回答的问题ID和答案 */
  answeredQuestions: Record<string, string>
  /** 当前选中的问题ID */
  selectedQuestionId: string | null
  /** 点击问题回调 */
  onSelectQuestion: (questionId: string) => void
}

export const QuestionList: React.FC<QuestionListProps> = ({
  questions,
  answeredQuestions,
  selectedQuestionId,
  onSelectQuestion
}) => {
  if (!questions || !Array.isArray(questions) || questions.length === 0) {
    return null
  }
  
  return (
    <div style={{ marginTop: 16 }}>
      <Text strong style={{ fontSize: 14, color: colors.textPrimary, marginBottom: 12, display: 'block' }}>
        需要补充以下信息：
      </Text>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        {questions.map((q, idx) => {
          if (!q || !q.id || !q.question) return null
          
          const isAnswered = !!answeredQuestions[q.id]
          const isSelected = selectedQuestionId === q.id
          
          return (
            <Card
              key={q.id}
              hoverable
              onClick={() => onSelectQuestion(q.id)}
              style={{
                cursor: 'pointer',
                border: isSelected 
                  ? `2px solid ${colors.primary}` 
                  : isAnswered 
                    ? `2px solid #52c41a` 
                    : `1px solid ${colors.border}`,
                background: isAnswered 
                  ? '#f6ffed' 
                  : isSelected 
                    ? colors.primaryLight 
                    : colors.bgSecondary,
                borderRadius: 8,
                transition: 'all 0.2s'
              }}
              bodyStyle={{ padding: '12px 16px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                  <span style={{ 
                    color: isAnswered ? '#52c41a' : colors.textSecondary,
                    fontWeight: 500,
                    minWidth: 24
                  }}>
                    {idx + 1}.
                  </span>
                  <Text 
                    style={{ 
                      color: isAnswered ? '#52c41a' : colors.textPrimary,
                      fontWeight: isSelected ? 600 : 400
                    }}
                  >
                    {q.question}
                  </Text>
                </div>
                {isAnswered && (
                  <CheckCircleOutlined 
                    style={{ 
                      color: '#52c41a', 
                      fontSize: 16,
                      marginLeft: 8
                    }} 
                  />
                )}
              </div>
              {isAnswered && (
                <div style={{ 
                  marginTop: 8, 
                  padding: '8px 12px', 
                  background: '#fff',
                  borderRadius: 4,
                  border: '1px solid #b7eb8f'
                }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>✓ 已回答</Text>
                </div>
              )}
            </Card>
          )
        })}
      </Space>
    </div>
  )
}

