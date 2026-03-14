/**
 * SolutionCard - 方案卡片组件
 * 展示单个改进方案，包含方案名称、标题、描述、建议列表、优缺点
 */
import React from 'react'
import { Card, Badge, Typography, Tag, Space } from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

const { Title, Text } = Typography

export interface ImprovementSuggestion {
  id: string
  title: string
  priority: 'high' | 'medium' | 'low'
}

export interface ImprovementSolution {
  id: string
  name: string  // 如"方案A"
  title: string
  suggestions: ImprovementSuggestion[]
  pros?: string
  cons?: string
  recommended?: boolean
}

interface SolutionCardProps {
  solution: ImprovementSolution
  selected?: boolean
  onSelect?: () => void
}

export const SolutionCard: React.FC<SolutionCardProps> = ({
  solution,
  selected = false,
  onSelect
}) => {
  const priorityColors: Record<string, string> = {
    high: '#ff4d4f',
    medium: '#faad14',
    low: '#52c41a'
  }

  const priorityText: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }

  return (
    <Card
      hoverable
      onClick={onSelect}
      style={{
        marginBottom: 16,
        border: selected 
          ? `2px solid ${colors.primary}` 
          : '1px solid #d9d9d9',
        borderRadius: 8,
        background: selected ? colors.primaryLight : '#fff',
        cursor: 'pointer',
        transition: 'all 0.2s'
      }}
      bodyStyle={{ padding: '20px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <Title level={4} style={{ margin: 0, color: selected ? colors.primary : colors.textPrimary }}>
          {solution.name}: {solution.title}
        </Title>
        {selected && (
          <CheckCircleOutlined style={{ fontSize: 20, color: colors.primary }} />
        )}
      </div>

      {solution.suggestions && solution.suggestions.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ fontSize: 14, marginBottom: 8, display: 'block' }}>
            完善建议：
          </Text>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {solution.suggestions.map((sug, idx) => (
              <li key={sug.id || idx} style={{ marginBottom: 8 }}>
                <Space>
                  <Text>{sug.title}</Text>
                  {sug.priority && (
                    <Tag color={priorityColors[sug.priority]}>
                      {priorityText[sug.priority]}优先级
                    </Tag>
                  )}
                </Space>
                {/* 不再显示详细描述，只显示标题 */}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 移除优缺点显示，用户自己判断 */}
    </Card>
  )
}

