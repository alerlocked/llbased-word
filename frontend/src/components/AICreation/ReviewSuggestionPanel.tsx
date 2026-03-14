/**
 * ReviewSuggestionPanel - 评审建议面板
 * 显示评审问题和修改建议，让用户选择是否接受
 */
import React, { useState } from 'react'
import { Card, List, Tag, Typography, Space, Checkbox, Button, Collapse, Alert } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, WarningOutlined } from '@ant-design/icons'
import { ReviewIssue, ReviewSuggestion } from '../../services/conversationService'

const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

interface ReviewSuggestionPanelProps {
  issues: ReviewIssue[]
  overallScore: number
  onApply?: (appliedSuggestionIds: string[], rejectedSuggestionIds: string[]) => void
}

export const ReviewSuggestionPanel: React.FC<ReviewSuggestionPanelProps> = ({
  issues,
  overallScore,
  onApply
}) => {
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set())

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'red'
      case 'medium': return 'orange'
      case 'low': return 'default'
      default: return 'default'
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'content': return 'purple'
      case 'structure': return 'blue'
      case 'language': return 'green'
      case 'logic': return 'orange'
      default: return 'default'
    }
  }

  const handleSuggestionToggle = (suggestionId: string) => {
    const newSet = new Set(selectedSuggestions)
    if (newSet.has(suggestionId)) {
      newSet.delete(suggestionId)
    } else {
      newSet.add(suggestionId)
    }
    setSelectedSuggestions(newSet)
  }

  const handleApply = () => {
    const appliedIds = Array.from(selectedSuggestions)
    const allSuggestionIds = issues.flatMap(issue => issue.suggestions.map(s => s.id))
    const rejectedIds = allSuggestionIds.filter(id => !appliedIds.includes(id))
    onApply?.(appliedIds, rejectedIds)
  }

  return (
    <div>
      <Alert
        message={`总体评分: ${(overallScore * 100).toFixed(0)}/100`}
        type={overallScore >= 0.7 ? 'success' : overallScore >= 0.5 ? 'warning' : 'error'}
        style={{ marginBottom: 16 }}
      />

      <Card
        title={<Title level={4}>评审建议</Title>}
        extra={
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={handleApply}
            disabled={selectedSuggestions.size === 0}
          >
            应用选中建议 ({selectedSuggestions.size})
          </Button>
        }
      >
        <Collapse>
          {issues.map(issue => (
            <Panel
              key={issue.id}
              header={
                <Space>
                  <Tag color={getSeverityColor(issue.severity)}>
                    {issue.severity}
                  </Tag>
                  <Tag color={getTypeColor(issue.type)}>
                    {issue.type}
                  </Tag>
                  <Text strong>{issue.description}</Text>
                  <Text type="secondary">({issue.location})</Text>
                </Space>
              }
            >
              <Paragraph>{issue.description}</Paragraph>

              <List
                dataSource={issue.suggestions}
                renderItem={(suggestion: ReviewSuggestion) => (
                  <List.Item>
                    <Space direction="vertical" style={{ width: '100%' }} size="small">
                      <Space>
                        <Checkbox
                          checked={selectedSuggestions.has(suggestion.id)}
                          onChange={() => handleSuggestionToggle(suggestion.id)}
                        />
                        <Text strong>{suggestion.description}</Text>
                      </Space>

                      {suggestion.example && (
                        <div style={{ marginLeft: 24 }}>
                          <Text type="secondary">示例：</Text>
                          <Text code>{suggestion.example}</Text>
                        </div>
                      )}

                      {suggestion.impact && (
                        <div style={{ marginLeft: 24 }}>
                          <Text type="secondary">预期效果：</Text>
                          <Text>{suggestion.impact}</Text>
                        </div>
                      )}
                    </Space>
                  </List.Item>
                )}
              />
            </Panel>
          ))}
        </Collapse>
      </Card>
    </div>
  )
}

