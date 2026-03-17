/**
 * FileList - 文件列表组件
 * 显示当前文件夹下的文件
 */
import { useState, useEffect } from 'react'
import { List, Image, Empty, Spin, message, Dropdown, Tag } from 'antd'
import {
  FileImageOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  MoreOutlined,
  DeleteOutlined,
  FolderOutlined
} from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

export interface MaterialFile {
  id: number
  name: string
  url: string
  type: string
  folderId?: string
  created_at: string
}

interface FileListProps {
  files: MaterialFile[]
  loading?: boolean
  currentFolder: string
  onSelect: (file: MaterialFile) => void
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

const FileList: React.FC<FileListProps> = ({
  files,
  loading = false,
  currentFolder,
  onSelect,
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
            onClick={() => onSelect(item)}
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
                    maxWidth: 200
                  }}>
                    {item.name}
                  </span>
                </div>
              }
              description={
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  {getFileTypeTag(item.type)}
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
