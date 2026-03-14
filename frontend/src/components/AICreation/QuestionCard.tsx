/**
 * QuestionCard - 问题卡片组件（带选项）
 * 用于显示需求分析中的询问问题
 */
import React from 'react'
import { Card, Radio, Input, Space, Typography } from 'antd'
import { Question, QuestionOption } from '../../services/conversationService'

const { TextArea } = Input
const { Text, Title } = Typography

interface QuestionCardProps {
  question: Question
  value?: string
  onChange?: (value: string, optionId?: string) => void
}

export const QuestionCard: React.FC<QuestionCardProps> = ({
  question,
  value,
  onChange
}) => {
  const [customAnswer, setCustomAnswer] = React.useState('')
  const [selectedOptionId, setSelectedOptionId] = React.useState<string>()

  const handleOptionChange = (optionId: string) => {
    setSelectedOptionId(optionId)
    const option = question.options.find(opt => opt.id === optionId)
    if (option) {
      onChange?.(option.text, optionId)
    }
  }

  const handleCustomChange = (text: string) => {
    setCustomAnswer(text)
    onChange?.(text)
  }

  return (
    <Card
      title={<Title level={5}>{question.question}</Title>}
      style={{ marginBottom: 16 }}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {question.options.length > 0 && (
          <Radio.Group
            value={selectedOptionId}
            onChange={(e) => handleOptionChange(e.target.value)}
          >
            <Space direction="vertical">
              {question.options.map(option => (
                <Radio key={option.id} value={option.id}>
                  <Text>{option.text}</Text>
                  {option.description && (
                    <Text type="secondary" style={{ display: 'block', marginLeft: 24 }}>
                      {option.description}
                    </Text>
                  )}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        )}

        {question.allow_custom && (
          <div>
            <Text strong>或自定义答案：</Text>
            <TextArea
              value={customAnswer}
              onChange={(e) => handleCustomChange(e.target.value)}
              placeholder="请输入您的答案"
              rows={3}
              style={{ marginTop: 8 }}
            />
          </div>
        )}
      </Space>
    </Card>
  )
}

