/**
 * FolderTree - 文件夹树形组件
 * 支持创建/删除/重命名文件夹，通过 API 持久化
 */
import { useState } from 'react'
import { Tree, Input, Dropdown, Modal, message } from 'antd'
import {
  FolderOutlined,
  FolderOpenOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  UserOutlined,
} from '@ant-design/icons'
import type { TreeDataNode, TreeProps } from 'antd'
import { colors } from '../../styles/design-tokens'

export interface FolderNode {
  key: string
  title: string
  children?: FolderNode[]
}

interface FolderTreeProps {
  folders: FolderNode[]
  selectedFolder: string | null
  onSelect: (folderKey: string) => void
  onCreate: (name: string, parentId?: number | null) => Promise<void>
  onRename: (folderId: number, name: string) => Promise<void>
  onDelete: (folderId: number) => Promise<void>
  /** Batch-learn all files in a folder as profile (N3) */
  onLearnFolder?: (folderKey: string) => void
}

const API_BASE = 'http://localhost:8000/api/creation'

const FolderTree: React.FC<FolderTreeProps> = ({
  folders,
  selectedFolder,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onLearnFolder,
}) => {
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [contextMenuNode, setContextMenuNode] = useState<FolderNode | null>(null)

  // Convert to Ant Design Tree format
  const convertToTreeData = (nodes: FolderNode[]): TreeDataNode[] => {
    return nodes.map(node => ({
      key: node.key,
      title: editingKey === node.key ? (
        <Input
          size="small"
          value={editingTitle}
          onChange={(e) => setEditingTitle(e.target.value)}
          onBlur={() => handleRenameSubmit(node.key)}
          onPressEnter={() => handleRenameSubmit(node.key)}
          autoFocus
          style={{ width: 120 }}
        />
      ) : (
        <span
          onContextMenu={(e) => {
            e.preventDefault()
            setContextMenuNode(node)
          }}
        >
          {node.title}
        </span>
      ),
      icon: ({ expanded }: { expanded: boolean }) =>
        expanded ? <FolderOpenOutlined /> : <FolderOutlined />,
      children: node.children ? convertToTreeData(node.children) : undefined
    }))
  }

  // Add folder — creates on server then refreshes
  const handleAddFolder = async (parentKey?: string) => {
    try {
      const parentId = parentKey ? Number(parentKey) : null
      await onCreate('新建文件夹', parentId)
      message.success('文件夹已创建')
    } catch {
      message.error('创建文件夹失败')
    }
  }

  // Rename folder
  const handleRenameSubmit = async (key: string) => {
    if (!editingTitle.trim()) {
      setEditingKey(null)
      return
    }

    try {
      await onRename(Number(key), editingTitle.trim())
      setEditingKey(null)
      setEditingTitle('')
      message.success('重命名成功')
    } catch {
      message.error('重命名失败')
    }
  }

  // Delete folder
  const handleDeleteFolder = (key: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个文件夹吗？文件夹内的文件不会被删除，将移动到根目录。',
      okText: '删除',
      cancelText: '取消',
      onOk: async () => {
        try {
          await onDelete(Number(key))
          if (selectedFolder === key) {
            onSelect('root')
          }
          message.success('文件夹已删除')
        } catch {
          message.error('删除文件夹失败')
        }
      }
    })
  }

  // Context menu
  const menuItems = contextMenuNode ? [
    {
      key: 'add',
      icon: <PlusOutlined />,
      label: '新建子文件夹',
      onClick: () => {
        handleAddFolder(contextMenuNode.key)
        setContextMenuNode(null)
      }
    },
    {
      key: 'rename',
      icon: <EditOutlined />,
      label: '重命名',
      onClick: () => {
        setEditingKey(contextMenuNode.key)
        setEditingTitle(contextMenuNode.title)
        setContextMenuNode(null)
      }
    },
    ...(onLearnFolder ? [{
      key: 'learn-folder',
      icon: <UserOutlined />,
      label: '批量学习为画像',
      onClick: () => {
        onLearnFolder(contextMenuNode.key)
        setContextMenuNode(null)
      }
    }] : []),
    { type: 'divider' as const },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除',
      danger: true,
      onClick: () => {
        handleDeleteFolder(contextMenuNode.key)
        setContextMenuNode(null)
      }
    }
  ] : []

  const treeData: TreeDataNode[] = [
    {
      key: 'root',
      title: '全部文件',
      icon: <FolderOpenOutlined />,
      children: convertToTreeData(folders)
    }
  ]

  const handleSelect: TreeProps['onSelect'] = (selectedKeys) => {
    if (selectedKeys.length > 0) {
      onSelect(selectedKeys[0] as string)
    }
  }

  return (
    <div style={{ padding: '8px 0' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 12px',
        borderBottom: `1px solid ${colors.borderLight}`
      }}>
        <span style={{ fontWeight: 500, color: colors.textPrimary }}>文件夹</span>
        <PlusOutlined
          style={{ color: colors.primary, cursor: 'pointer' }}
          onClick={() => handleAddFolder()}
          title="新建文件夹"
        />
      </div>

      <Dropdown
        menu={{ items: menuItems }}
        trigger={['contextMenu']}
        open={!!contextMenuNode}
        onOpenChange={(open) => !open && setContextMenuNode(null)}
      >
        <div>
          <Tree
            showIcon
            blockNode
            selectedKeys={[selectedFolder || 'root']}
            treeData={treeData}
            onSelect={handleSelect}
            style={{ background: 'transparent' }}
          />
        </div>
      </Dropdown>
    </div>
  )
}

export default FolderTree
