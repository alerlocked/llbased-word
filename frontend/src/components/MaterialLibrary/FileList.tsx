/**
 * FileList - 文件列表组件
 * 显示当前文件夹下的文件
 *
 * 交互行为：
 * - 点击文件 → 预览文件
 * - 点击"添加引用"按钮 → 添加引用到编辑栏
 */
import { useState } from 'react'
import { List, Image, Empty, Spin, Dropdown, Tag, Button, Modal, Space, Tooltip } from 'antd'
import {
  FileImageOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  DeleteOutlined,
  FolderOutlined,
  PlusOutlined,
  EyeOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  UserOutlined
} from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

export interface MaterialFile {
  id: number
  name: string
  url: string
  type: string
  folderId?: string
  created_at: string
  content?: string
  domain?: string  // Process type: assembly, welding, coating, general
  parse_status?: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'unknown'
  parse_progress?: number  // 0-100
  parse_error?: string
}

interface FileListProps {
  files: MaterialFile[]
  loading?: boolean
  currentFolder: string
  onPreview: (file: MaterialFile) => void  // preview file
  onInsert: (file: MaterialFile) => void   // add reference to editor
  onLearnProfile?: (file: MaterialFile) => void  // learn as user profile
  onDelete?: (fileId: number) => void
  onMove?: (fileId: number, folderId: string) => void
  folders: { key: string; title: string }[]
}

// 获取文件图标
const getFileIcon = (type: string) => {
  if (type.startsWith('image/')) {
    return <FileImageOutlined style={{ fontSize: 24, color: colors.primary }} />
  }
  if (type === 'pdf' || type === 'application/pdf') {
    return <FilePdfOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
  }
  if (type.includes('word') || type === 'docx') {
    return <FileWordOutlined style={{ fontSize: 24, color: '#1890ff' }} />
  }
  return <FileTextOutlined style={{ fontSize: 24, color: colors.textSecondary }} />
}

// 获取文件类型标签
const getFileTypeTag = (type: string) => {
  if (type.startsWith('image/')) {
    return <Tag color="blue">图片</Tag>
  }
  if (type === 'pdf' || type === 'application/pdf') {
    return <Tag color="red">PDF</Tag>
  }
  if (type.includes('word') || type === 'docx') {
    return <Tag color="blue">Word</Tag>
  }
  return <Tag>文档</Tag>
}

// 获取解析状态标签
const getParseStatusTag = (status?: string, error?: string, progress?: number) => {
  if (!status || status === 'unknown') {
    return null
  }

  switch (status) {
    case 'pending':
    case 'queued':
      return (
        <Tag color="default" icon={<ClockCircleOutlined />}>
          等待解析
        </Tag>
      )
    case 'processing':
      return (
        <Tag color="processing" icon={<SyncOutlined spin />}>
          解析中 {progress != null && progress > 0 ? `${progress}%` : ''}
        </Tag>
      )
    case 'completed':
      return (
        <Tag color="success" icon={<CheckCircleOutlined />}>
          已解析
        </Tag>
      )
    case 'failed':
      return (
        <Tooltip title={error || '解析失败'}>
          <Tag color="error" icon={<CloseCircleOutlined />}>
            解析失败
          </Tag>
        </Tooltip>
      )
    default:
      return null
  }
}

const FileList: React.FC<FileListProps> = ({
  files,
  loading = false,
  currentFolder,
  onPreview,
  onInsert,
  onLearnProfile,
  onDelete,
  onMove,
  folders
}) => {
  const [contextMenuFile, setContextMenuFile] = useState<MaterialFile | null>(null)

  // 过滤当前文件夹的文件
  const filteredFiles = currentFolder === 'root'
    ? files.filter(f => !f.folderId)
    : files.filter(f => f.folderId === currentFolder)

  // 移动文件菜单项
  const moveMenuItems = folders
    .filter(f => f.key !== currentFolder)
    .map(f => ({
      key: f.key,
      label: (
        <span>
          <FolderOutlined style={{ marginRight: 8 }} />
          {f.title}
        </span>
      ),
      onClick: () => {
        if (contextMenuFile && onMove) {
          onMove(contextMenuFile.id, f.key)
          setContextMenuFile(null)
        }
      }
    }))

  const menuItems = [
    {
      key: 'preview',
      icon: <EyeOutlined />,
      label: '预览',
      onClick: () => {
        if (contextMenuFile) {
          onPreview(contextMenuFile)
          setContextMenuFile(null)
        }
      }
    },
    {
      key: 'insert',
      icon: <PlusOutlined />,
      label: '添加引用',
      onClick: () => {
        if (contextMenuFile) {
          onInsert(contextMenuFile)
          setContextMenuFile(null)
        }
      }
    },
    ...(onLearnProfile ? [{
      key: 'learn-profile',
      icon: <UserOutlined />,
      label: '学习为画像',
      onClick: () => {
        if (contextMenuFile) {
          onLearnProfile(contextMenuFile)
          setContextMenuFile(null)
        }
      }
    }] : []),
    { type: 'divider' as const },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除',
      danger: true,
      onClick: () => {
        if (contextMenuFile && onDelete) {
          onDelete(contextMenuFile.id)
          setContextMenuFile(null)
        }
      }
    },
    ...(moveMenuItems.length > 0 ? [
      { type: 'divider' as const },
      {
        key: 'move',
        icon: <FolderOutlined />,
        label: '移动到',
        children: moveMenuItems
      }
    ] : [])
  ]

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Spin />
      </div>
    )
  }

  if (filteredFiles.length === 0) {
    return (
      <Empty
        description={currentFolder === 'root' ? '暂无文件' : '此文件夹为空'}
        style={{ padding: 40 }}
      />
    )
  }

  return (
    <List
      dataSource={filteredFiles}
      renderItem={(item) => (
        <Dropdown
          menu={{ items: menuItems }}
          trigger={['contextMenu']}
          onOpenChange={(open) => !open && setContextMenuFile(null)}
        >
          <List.Item
            onClick={() => onPreview(item)}
            onContextMenu={() => setContextMenuFile(item)}
            style={{
              cursor: 'pointer',
              padding: '12px 16px',
              borderRadius: 8,
              marginBottom: 4,
              transition: 'background 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = colors.bgSecondary
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <List.Item.Meta
              avatar={
                item.type.startsWith('image/') ? (
                  <Image
                    src={item.url}
                    width={48}
                    height={48}
                    style={{ objectFit: 'cover', borderRadius: 4 }}
                    preview={false}
                  />
                ) : (
                  <div style={{
                    width: 48,
                    height: 48,
                    background: colors.bgTertiary,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 4
                  }}>
                    {getFileIcon(item.type)}
                  </div>
                )
              }
              title={
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: 160
                  }}>
                    {item.name}
                  </span>
                  <Button
                    type="text"
                    size="small"
                    icon={<PlusOutlined />}
                    onClick={(e) => {
                      e.stopPropagation()
                      onInsert(item)
                    }}
                    title="添加引用到编辑栏"
                    style={{ color: colors.primary }}
                  />
                  {onLearnProfile && (
                    <Tooltip title="学习为画像">
                      <Button
                        type="text"
                        size="small"
                        icon={<UserOutlined />}
                        onClick={(e) => {
                          e.stopPropagation()
                          onLearnProfile(item)
                        }}
                        style={{ color: colors.textSecondary }}
                      />
                    </Tooltip>
                  )}
                </div>
              }
              description={
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  {getFileTypeTag(item.type)}
                  {getParseStatusTag(item.parse_status, item.parse_error, item.parse_progress)}
                  <span style={{ fontSize: 12, color: colors.textTertiary }}>
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>
              }
            />
          </List.Item>
        </Dropdown>
      )}
    />
  )
}

export default FileList
