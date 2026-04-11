import { useState, useEffect } from 'react'
import { Drawer, List, Button, Typography, Space, message, Tag } from 'antd'
import { HistoryOutlined, RollbackOutlined } from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'
import { draftApi, type DraftVersion } from '../../services/draftApi'
import dayjs from 'dayjs'

const { Text } = Typography

/**
 * 版本历史组件
 * 显示初稿版本列表，支持回滚，适配 DraftVersion 数据结构
 */

export interface EditorVersion {
  id: number
  project_id: number
  content: string
  diff?: any
  operation: 'ai_draft' | 'ai_rewrite' | 'manual_edit'
  created_at: string
}

/**
 * 快照来源标签映射
 */
const SOURCE_TAG_MAP: Record<string, { label: string; color: string }> = {
  upload: { label: '上传', color: 'blue' },
  user_edit: { label: '用户编辑', color: 'green' },
  ai_completion: { label: 'AI补全', color: 'purple' },
  rollback: { label: '回滚', color: 'orange' },
}

interface VersionHistoryProps {
  projectId: number
  draftId?: number
  visible: boolean
  onClose: () => void
  onRollback: (versionId: number) => Promise<void>
  /**
   * 模式：draft 使用 Draft API，creation 使用旧接口
   * @default 'draft'
   */
  mode?: 'draft' | 'creation'
}

const VersionHistory: React.FC<VersionHistoryProps> = ({
  projectId,
  draftId,
  visible,
  onClose,
  onRollback,
  mode = 'draft'
}) => {
  const { colors } = useTheme()
  const [versions, setVersions] = useState<EditorVersion[]>([])
  const [draftVersions, setDraftVersions] = useState<DraftVersion[]>([])
  const [loading, setLoading] = useState(false)

  /**
   * 加载版本历史
   */
  useEffect(() => {
    if (visible) {
      if (mode === 'draft' && draftId) {
        loadDraftVersions()
      } else if (projectId) {
        loadCreationVersions()
      }
    }
  }, [visible, projectId, draftId, mode])

  /**
   * 加载初稿版本（Draft API）
   */
  const loadDraftVersions = async () => {
    if (!draftId) return
    setLoading(true)
    try {
      const data = await draftApi.listVersions(draftId)
      setDraftVersions(data.versions || [])
    } catch (error) {
      console.error('加载初稿版本历史失败:', error)
    } finally {
      setLoading(false)
    }
  }

  /**
   * 加载创作版本（旧接口）
   */
  const loadCreationVersions = async () => {
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
      if (mode === 'draft' && draftId) {
        await draftApi.rollback(draftId, versionId)
      }
      await onRollback(versionId)
      message.success('已回滚到该版本')
      onClose()
    } catch (error) {
      message.error('回滚失败')
    }
  }

  /**
   * 渲染初稿版本列表
   */
  const renderDraftVersion = (version: DraftVersion) => {
    const sourceInfo = SOURCE_TAG_MAP[version.snapshot_source] || { label: version.snapshot_source, color: 'default' }
    return (
      <List.Item
        actions={[
          <Button
            key="rollback"
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
              <Tag color={sourceInfo.color}>{sourceInfo.label}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {dayjs(version.created_at).format('YYYY-MM-DD HH:mm:ss')}
              </Text>
            </Space>
          }
          description={
            <Text
              type="secondary"
              ellipsis={{ tooltip: version.snapshot_content }}
              style={{ fontSize: 12 }}
            >
              {version.snapshot_content.substring(0, 100)}...
            </Text>
          }
        />
      </List.Item>
    )
  }

  /**
   * 渲染创作版本列表
   */
  const renderCreationVersion = (version: EditorVersion) => (
    <List.Item
      actions={[
        <Button
          key="rollback"
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
  )

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
      {mode === 'draft' ? (
        <List
          loading={loading}
          dataSource={draftVersions}
          renderItem={(version) => renderDraftVersion(version)}
        />
      ) : (
        <List
          loading={loading}
          dataSource={versions}
          renderItem={(version) => renderCreationVersion(version)}
        />
      )}
    </Drawer>
  )
}

export default VersionHistory

