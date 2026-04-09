/**
 * PortraitDetail - 画像详情展示组件
 * 展示六维画像详情，支持编辑模式切换
 */
import { useState, useEffect } from 'react'
import { Card, Typography, Tag, Space, Button, Divider, Descriptions, Spin, message, Tabs } from 'antd'
import { EditOutlined, HistoryOutlined, CopyOutlined } from '@ant-design/icons'
import { getPortrait, updatePortrait, StylePortrait } from '../../services/styleService'
import PortraitEditor from './PortraitEditor'

const { Title, Text, Paragraph } = Typography
const { TabPane } = Tabs

interface PortraitDetailProps {
  portraitId: number
  userId?: number
  editable?: boolean
  onUpdate?: (portrait: StylePortrait) => void
}

export const PortraitDetail: React.FC<PortraitDetailProps> = ({
  portraitId,
  userId,
  editable = false,
  onUpdate
}) => {
  const [portrait, setPortrait] = useState<StylePortrait | null>(null)
  const [loading, setLoading] = useState(false)
  const [editMode, setEditMode] = useState(false)

  const fetchPortrait = async () => {
    setLoading(true)
    try {
      const data = await getPortrait(portraitId)
      setPortrait(data)
    } catch (error) {
      message.error('获取画像详情失败')
      console.error('获取画像失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (portraitId) {
      fetchPortrait()
    }
  }, [portraitId])

  const handleSave = async (updatedPortrait: StylePortrait) => {
    try {
      if (userId) {
        // 更新后端
        const result = await updatePortrait(portraitId, updatedPortrait)
        setPortrait(result.portrait)
      } else {
        // 仅更新本地状态
        setPortrait(updatedPortrait)
      }
      setEditMode(false)
      if (onUpdate) {
        onUpdate(updatedPortrait)
      }
      message.success('画像已更新')
    } catch (error) {
      message.error('更新失败')
      console.error('更新失败:', error)
    }
  }

  const handleCopy = () => {
    if (portrait) {
      navigator.clipboard.writeText(JSON.stringify(portrait, null, 2))
      message.success('已复制到剪贴板')
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!portrait) {
    return (
      <Card>
        <Text type="secondary">画像不存在</Text>
      </Card>
    )
  }

  if (editMode && editable) {
    return (
      <PortraitEditor
        portrait={portrait}
        portraitId={portraitId}
        userId={userId}
        onSave={handleSave}
        onCancel={() => setEditMode(false)}
      />
    )
  }

  return (
    <div>
      <Card
        title={
          <Space>
            <Title level={4} style={{ margin: 0 }}>画像详情</Title>
            <Tag color="blue">v{portrait.version}</Tag>
            <Tag color={portrait.confidence_score >= 0.8 ? 'green' : portrait.confidence_score >= 0.6 ? 'orange' : 'red'}>
              置信度: {(portrait.confidence_score * 100).toFixed(1)}%
            </Tag>
            <Tag>{portrait.source === 'auto' ? '自动生成' : portrait.source === 'manual' ? '手动创建' : '混合'}</Tag>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<CopyOutlined />} onClick={handleCopy}>
              复制JSON
            </Button>
            {editable && (
              <Button type="primary" icon={<EditOutlined />} onClick={() => setEditMode(true)}>
                编辑
              </Button>
            )}
          </Space>
        }
      >
        <Tabs defaultActiveKey="overview">
          <TabPane tab="风格概述" key="overview">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="概述" span={2}>
                {portrait.style_overview.summary}
              </Descriptions.Item>
              <Descriptions.Item label="标签" span={2}>
                <Space wrap>
                  {portrait.style_overview.tags.map(tag => (
                    <Tag key={tag}>{tag}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="语气参数">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.style_overview.formality_constraint, null, 2)}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="段落约束">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.style_overview.paragraph_constraint, null, 2)}
                </pre>
              </Descriptions.Item>
            </Descriptions>
          </TabPane>

          <TabPane tab="创作方法论" key="methodology">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="核心方法" span={2}>
                {portrait.methodology.approach}
              </Descriptions.Item>
              <Descriptions.Item label="类比规则">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.methodology.analogy_rule, null, 2)}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="结构模板">
                {portrait.methodology.structure_template || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="强制模式" span={2}>
                <Space wrap>
                  {portrait.methodology.mandatory_patterns.map(pattern => (
                    <Tag key={pattern}>{pattern}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </TabPane>

          <TabPane tab="思维内核" key="thinking">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="核心价值观" span={2}>
                <Space wrap>
                  {portrait.thinking_core.values.map(value => (
                    <Tag key={value} color="blue">{value}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="价值判断函数">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.thinking_core.value_judgment_function, null, 2)}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="逻辑模式">
                <Space wrap>
                  {portrait.thinking_core.logic_patterns.map(pattern => (
                    <Tag key={pattern}>{pattern}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="论证规则">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.thinking_core.argumentation_rules, null, 2)}
                </pre>
              </Descriptions.Item>
            </Descriptions>
          </TabPane>

          <TabPane tab="表达特征" key="expression">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="正式程度">
                {portrait.expression_features.formality_level}
              </Descriptions.Item>
              <Descriptions.Item label="句式约束">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.expression_features.sentence_constraints, null, 2)}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="开场习惯">
                <Space wrap>
                  {portrait.expression_features.opening_habits.map(habit => (
                    <Tag key={habit}>{habit}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="高频词">
                <Space wrap>
                  {portrait.expression_features.keywords.map(keyword => (
                    <Tag key={keyword}>{keyword}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="句式长短比">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.expression_features.sentence_length_ratio, null, 2)}
                </pre>
              </Descriptions.Item>
            </Descriptions>
          </TabPane>

          <TabPane tab="创作习惯" key="habits">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="开场短语模板" span={2}>
                <Space wrap>
                  {portrait.writing_habits.opening_phrases.map(phrase => (
                    <Tag key={phrase} color="purple">{phrase}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="开场规则">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.writing_habits.opening_rule, null, 2)}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="段落长度偏好">
                {portrait.writing_habits.paragraph_length_preference || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="过渡模式">
                <Space wrap>
                  {portrait.writing_habits.transition_patterns.map(pattern => (
                    <Tag key={pattern}>{pattern}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="结尾模式">
                <Space wrap>
                  {portrait.writing_habits.closing_patterns.map(pattern => (
                    <Tag key={pattern}>{pattern}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </TabPane>

          <TabPane tab="独特标记" key="markers">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="背景信息" span={2}>
                {portrait.unique_markers.background || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="专业领域">
                <Space wrap>
                  {portrait.unique_markers.expertise.map(exp => (
                    <Tag key={exp} color="cyan">{exp}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="身份锚定框架">
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(portrait.unique_markers.identity_framework, null, 2)}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="视角规则" span={2}>
                <Space wrap>
                  {portrait.unique_markers.perspective_rules.map(rule => (
                    <Tag key={rule}>{rule}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </TabPane>

          <TabPane tab="元数据" key="metadata">
            <Descriptions column={2} variant="bordered">
              <Descriptions.Item label="版本">{portrait.version}</Descriptions.Item>
              <Descriptions.Item label="置信度">
                {(portrait.confidence_score * 100).toFixed(1)}%
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {portrait.source === 'auto' ? '自动生成' : portrait.source === 'manual' ? '手动创建' : '混合'}
              </Descriptions.Item>
              <Descriptions.Item label="最后更新">
                {portrait.last_updated ? new Date(portrait.last_updated).toLocaleString('zh-CN') : '-'}
              </Descriptions.Item>
            </Descriptions>
          </TabPane>
        </Tabs>
      </Card>
    </div>
  )
}

export default PortraitDetail
