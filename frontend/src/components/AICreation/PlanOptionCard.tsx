/**
 * PlanOptionCard - 计划选项卡片
 * 用于显示和选择不同的计划选项
 */
import React from 'react'
import { Card, Button, Tag, Space, Typography, Divider } from 'antd'
import { CheckOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { PlanOption } from '../../services/conversationService'

const { Text, Title, Paragraph } = Typography

interface PlanOptionCardProps {
  option: PlanOption
  selected?: boolean
  onSelect?: () => void
  onExplain?: () => void
}

export const PlanOptionCard: React.FC<PlanOptionCardProps> = ({
  option,
  selected,
  onSelect,
  onExplain
}) => {
  return (
    <Card
      hoverable
      style={{
        marginBottom: 16,
        border: selected ? '2px solid #1890ff' : '1px solid #d9d9d9',
        cursor: 'pointer'
      }}
      onClick={onSelect}
      actions={[
        <Button
          key="select"
          type={selected ? 'primary' : 'default'}
          icon={<CheckOutlined />}
          onClick={(e) => {
            e.stopPropagation()
            onSelect?.()
          }}
        >
          {selected ? '已选择' : '选择此方案'}
        </Button>,
        <Button
          key="explain"
          type="link"
          icon={<InfoCircleOutlined />}
          onClick={(e) => {
            e.stopPropagation()
            onExplain?.()
          }}
        >
          查看详情
        </Button>
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Title level={4}>{option.title}</Title>
        
        <div>
          <Text strong>切入角度：</Text>
          <Text>{option.angle}</Text>
        </div>

        <div>
          <Text strong>文章结构：</Text>
          <ul style={{ marginTop: 8, marginBottom: 0 }}>
            {option.structure.map((item, index) => (
              <li key={index}>
                <Text>{item}</Text>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <Text strong>重点内容：</Text>
          <Text>{option.focus}</Text>
        </div>

        <Space>
          <Tag color="blue">预估字数: {option.estimated_words}</Tag>
        </Space>

        <Divider style={{ margin: '12px 0' }} />

        <div>
          <Text strong>优点：</Text>
          <Text type="success">{option.pros}</Text>
        </div>

        <div>
          <Text strong>缺点：</Text>
          <Text type="warning">{option.cons}</Text>
        </div>
      </Space>
    </Card>
  )
}

