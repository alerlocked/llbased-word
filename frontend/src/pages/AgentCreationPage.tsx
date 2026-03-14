/**
 * AgentCreationPage - AI Agent智能创作页面
 * 使用LangChain Agent自动生成文章
 */
import { useState, useEffect } from 'react'
import { Card, Input, Button, Steps, Progress, Space, Typography, Divider, message, Spin } from 'antd'
import { RocketOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import MainLayout from '../components/Layout/MainLayout'

const { TextArea } = Input
const { Title, Paragraph, Text } = Typography

interface TaskStatus {
  task_id?: string
  status: string
  progress: number
  result?: {
    content: string
    intermediate_steps: any[]
  }
  error?: string
}

const AgentCreationPage: React.FC = () => {
  const [input, setInput] = useState('')
  const [taskId, setTaskId] = useState<string | null>(null)
  const [status, setStatus] = useState<TaskStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [polling, setPolling] = useState(false)

  // 轮询任务状态
  useEffect(() => {
    if (!taskId || !polling) return

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/agent/task/${taskId}`)
        if (response.ok) {
          const data = await response.json()
          setStatus(data)

          // 任务完成或失败，停止轮询
          if (data.status === 'completed' || data.status === 'failed') {
            setPolling(false)
            setLoading(false)
            
            if (data.status === 'completed') {
              message.success('文章生成完成！')
            } else {
              message.error(`生成失败: ${data.error || '未知错误'}`)
            }
          }
        }
      } catch (error) {
        console.error('轮询任务状态失败:', error)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [taskId, polling])

  // 开始生成
  const handleGenerate = async () => {
    if (!input.trim()) {
      message.warning('请输入创作需求')
      return
    }

    setLoading(true)
    setStatus(null)
    setTaskId(null)

    try {
      const response = await fetch('http://localhost:8000/api/agent/generate-article', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_input: input,
          user_id: 1 // TODO: 从用户上下文获取
        })
      })

      if (response.ok) {
        const data = await response.json()
        setTaskId(data.task_id)
        setPolling(true)
        message.info('任务已启动，正在生成中...')
      } else {
        message.error('启动任务失败')
        setLoading(false)
      }
    } catch (error) {
      console.error('启动生成任务失败:', error)
      message.error('网络错误')
      setLoading(false)
    }
  }

  // 获取当前步骤
  const getCurrentStep = () => {
    if (!status) return 0
    const progress = status.progress
    if (progress < 20) return 0
    if (progress < 40) return 1
    if (progress < 60) return 2
    if (progress < 80) return 3
    return 4
  }

  // 复制内容
  const handleCopy = () => {
    if (status?.result?.content) {
      navigator.clipboard.writeText(status.result.content)
      message.success('已复制到剪贴板')
    }
  }

  return (
    <MainLayout>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px' }}>
        <Title level={2}>🤖 AI Agent 智能创作</Title>
        <Paragraph type="secondary">
          告诉AI你的创作需求，Agent会自动分析、搜索素材、生成大纲并撰写完整文章
        </Paragraph>

        <Card style={{ marginBottom: 24 }}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              <Text strong>创作需求</Text>
              <TextArea
                rows={6}
                placeholder="例如：写一篇关于某村传统水利工程保护的报道，1500字左右，要包含：&#10;1. 历史背景和文化价值&#10;2. 当前保护现状&#10;3. 面临的挑战&#10;4. 专家观点和建议&#10;5. 未来展望"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                style={{ marginTop: 8 }}
              />
            </div>

            <Button
              type="primary"
              size="large"
              icon={loading ? <LoadingOutlined /> : <RocketOutlined />}
              onClick={handleGenerate}
              loading={loading}
              disabled={loading}
              block
            >
              {loading ? '生成中...' : '开始智能创作'}
            </Button>
          </Space>
        </Card>

        {/* 进度显示 */}
        {status && (
          <Card title="生成进度" style={{ marginBottom: 24 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              <Steps
                current={getCurrentStep()}
                items={[
                  {
                    title: '需求分析',
                    icon: status.progress >= 20 ? <CheckCircleOutlined /> : undefined
                  },
                  {
                    title: '素材检索',
                    icon: status.progress >= 40 ? <CheckCircleOutlined /> : undefined
                  },
                  {
                    title: '生成大纲',
                    icon: status.progress >= 60 ? <CheckCircleOutlined /> : undefined
                  },
                  {
                    title: '撰写内容',
                    icon: status.progress >= 80 ? <CheckCircleOutlined /> : undefined
                  },
                  {
                    title: '质量评审',
                    icon: status.progress >= 100 ? <CheckCircleOutlined /> : undefined
                  }
                ]}
              />

              <Progress
                percent={status.progress}
                status={status.status === 'failed' ? 'exception' : status.status === 'completed' ? 'success' : 'active'}
              />

              {status.status === 'processing' && (
                <div style={{ textAlign: 'center' }}>
                  <Spin tip="AI Agent正在工作中，请稍候..." />
                </div>
              )}
            </Space>
          </Card>
        )}

        {/* 生成结果 */}
        {status?.status === 'completed' && status.result?.content && (
          <Card
            title="生成结果"
            extra={
              <Button type="primary" onClick={handleCopy}>
                复制内容
              </Button>
            }
          >
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
              {status.result.content}
            </div>

            {status.result.intermediate_steps && status.result.intermediate_steps.length > 0 && (
              <>
                <Divider />
                <details>
                  <summary style={{ cursor: 'pointer', color: '#1890ff' }}>
                    查看生成过程详情
                  </summary>
                  <div style={{ marginTop: 16, padding: 16, background: '#f5f5f5', borderRadius: 4 }}>
                    <pre style={{ margin: 0, fontSize: 12 }}>
                      {JSON.stringify(status.result.intermediate_steps, null, 2)}
                    </pre>
                  </div>
                </details>
              </>
            )}
          </Card>
        )}

        {/* 错误显示 */}
        {status?.status === 'failed' && (
          <Card>
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <CloseCircleOutlined style={{ fontSize: 48, color: '#ff4d4f' }} />
              <Title level={4} style={{ marginTop: 16 }}>生成失败</Title>
              <Text type="danger">{status.error || '未知错误'}</Text>
              <div style={{ marginTop: 24 }}>
                <Button type="primary" onClick={() => setStatus(null)}>
                  重新尝试
                </Button>
              </div>
            </div>
          </Card>
        )}

        {/* 使用提示 */}
        <Card title="💡 使用提示" style={{ marginTop: 24 }}>
          <Space direction="vertical">
            <Text>1. <strong>明确需求：</strong>清楚描述主题、字数、体裁和要求</Text>
            <Text>2. <strong>多角度：</strong>可以指定从历史、地理、经济、文化等角度分析</Text>
            <Text>3. <strong>具体要素：</strong>说明需要包含的内容（如数据、专家观点、案例等）</Text>
            <Text>4. <strong>风格要求：</strong>可以指定正式/口语化、客观/主观等风格</Text>
            <Text>5. <strong>耐心等待：</strong>Agent需要时间分析、搜索和生成，通常需要1-3分钟</Text>
          </Space>
        </Card>
      </div>
    </MainLayout>
  )
}

export default AgentCreationPage

