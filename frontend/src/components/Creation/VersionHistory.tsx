import { useState, useEffect } from 'react'
import { Drawer, List, Button, Typography, Space, message } from 'antd'
import { HistoryOutlined, RollbackOutlined } from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'
import dayjs from 'dayjs'

const { Text } = Typography

/**
 * 版本历史组件
 * 显示编辑器版本列表,支持回滚
 */

export interface EditorVersion {
  id: number
  project_id: number
  content: string
  diff?: any
  operation: 'ai_draft' | 'ai_rewrite' | 'manual_edit'
  created_at: string
}

interface VersionHistoryProps {
  projectId: number
  visible: boolean
  onClose: () => void
  onRollback: (versionId: number) => Promise<void>
}

const VersionHistory: React.FC<VersionHistoryProps> = ({
  projectId,
  visible,
  onClose,
  onRollback
}) => {
  const { colors } = useTheme()
  const [versions, setVersions] = useState<EditorVersion[]>([])
  const [loading, setLoading] = useState(false)

  /**
   * 加载版本历史
   */
  useEffect(() => {
    if (visible && projectId) {
      loadVersions()
    }
  }, [visible, projectId])

  const loadVersions = async () => {
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/versions`)
      if (response.ok) {
        const data = await response.json()
        setVersions(data.versions || [])
      }
    } catch (error) {
      console.error('加载版本历史失败:', error)
    } finally {
      setLoading(false)
    }
  }

  /**
   * 格式化操作类型
   */
  const formatOperation = (operation: string) => {
    const operations = {
      ai_draft: 'AI生成初稿',
      ai_rewrite: 'AI改写',
      manual_edit: '手动编辑'
    }
    return operations[operation as keyof typeof operations] || operation
  }

  /**
   * 处理回滚
   */
  const handleRollback = async (versionId: number) => {
    try {
      await onRollback(versionId)
      message.success('已回滚到该版本')
      onClose()
    } catch (error) {
      message.error('回滚失败')
    }
  }

  return (
    <Drawer
      title={
        <Space>
          <HistoryOutlined />
          <span>版本历史</span>
        </Space>
      }
      open={visible}
      onClose={onClose}
      width={400}
    >
      <List
        loading={loading}
        dataSource={versions}
        renderItem={(version) => (
          <List.Item
            actions={[
              <Button
                type="link"
                icon={<RollbackOutlined />}
                onClick={() => handleRollback(version.id)}
              >
                回滚
              </Button>
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <Text strong>{formatOperation(version.operation)}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {dayjs(version.created_at).format('YYYY-MM-DD HH:mm:ss')}
                  </Text>
                </Space>
              }
              description={
                <Text
                  type="secondary"
                  ellipsis={{ tooltip: version.content }}
                  style={{ fontSize: 12 }}
                >
                  {version.content.substring(0, 100)}...
                </Text>
              }
            />
          </List.Item>
        )}
      />
    </Drawer>
  )
}

export default VersionHistory

