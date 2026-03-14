/**
 * MaterialReportView - 素材报告视图
 * 显示素材报告，包括素材列表、推荐组合等
 */
import React from 'react'
import { Card, List, Tag, Typography, Space, Checkbox, Button } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { MaterialReport, MaterialItem } from '../../services/conversationService'

const { Title, Text, Paragraph } = Typography

interface MaterialReportViewProps {
  report: MaterialReport
  selectedIds?: string[]
  onSelect?: (materialId: string, selected: boolean) => void
  onConfirm?: () => void
}

export const MaterialReportView: React.FC<MaterialReportViewProps> = ({
  report,
  selectedIds = [],
  onSelect,
  onConfirm
}) => {
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'red'
      case 'medium': return 'orange'
      case 'low': return 'default'
      default: return 'default'
    }
  }

  return (
    <div>
      {report.summary && (
        <Card style={{ marginBottom: 16 }}>
          <Paragraph>{report.summary}</Paragraph>
        </Card>
      )}

      <Card
        title={<Title level={4}>素材列表</Title>}
        extra={
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={onConfirm}
          >
            确认使用
          </Button>
        }
      >
        <List
          dataSource={report.materials}
          renderItem={(material: MaterialItem) => (
            <List.Item>
              <Space direction="vertical" style={{ width: '100%' }} size="small">
                <Space>
                  <Checkbox
                    checked={selectedIds.includes(material.id)}
                    onChange={(e) => onSelect?.(material.id, e.target.checked)}
                  />
                  <Title level={5} style={{ margin: 0 }}>
                    {material.title}
                  </Title>
                  <Tag color={getPriorityColor(material.priority)}>
                    {material.priority}
                  </Tag>
                  {material.relevance_score && (
                    <Tag>相关性: {(material.relevance_score * 100).toFixed(0)}%</Tag>
                  )}
                </Space>

                <Text type="secondary">来源: {material.source}</Text>

                <Paragraph ellipsis={{ rows: 2, expandable: true }}>
                  {material.content}
                </Paragraph>

                <div>
                  <Text strong>价值说明：</Text>
                  <Text>{material.value_description}</Text>
                </div>
              </Space>
            </List.Item>
          )}
        />
      </Card>

      {report.recommendations.length > 0 && (
        <Card title={<Title level={4}>推荐素材</Title>} style={{ marginTop: 16 }}>
          <Space wrap>
            {report.recommendations.map(id => (
              <Tag key={id} color="green">
                {report.materials.find(m => m.id === id)?.title || id}
              </Tag>
            ))}
          </Space>
        </Card>
      )}
    </div>
  )
}

