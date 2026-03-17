/**
 * FolderTree - 文件夹树形组件
 * 支持创建/删除/重命名文件夹
 */
import { useState, useEffect } from 'react'
import { Tree, Input, Dropdown, Modal, message } from 'antd'
import {
  FolderOutlined,
  FolderOpenOutlined,
  FileOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  MoreOutlined
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
  onUpdate: (folders: FolderNode[]) => void
}

const FolderTree: React.FC<FolderTreeProps> = ({
  folders,
  selectedFolder,
  onSelect,
  onUpdate
}) => {
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [contextMenuNode, setContextMenuNode] = useState<FolderNode | null>(null)

  // 转换为 Ant Design Tree 格式
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

  // 生成唯一 key
  const generateKey = () => `folder_${Date.now()}`

  // 添加文件夹
  const handleAddFolder = (parentKey?: string) => {
    const newFolder: FolderNode = {
      key: generateKey(),
      title: '新建文件夹',
      children: []
    }

    let newFolders: FolderNode[]
    if (parentKey) {
      // 添加到指定父文件夹
      newFolders = addToFolder(folders, parentKey, newFolder)
    } else {
      // 添加到根级别
      newFolders = [...folders, newFolder]
    }

    onUpdate(newFolders)
    setEditingKey(newFolder.key)
    setEditingTitle(newFolder.title)
    message.success('文件夹已创建')
  }

  // 递归添加到指定文件夹
  const addToFolder = (
    nodes: FolderNode[],
    parentKey: string,
    newFolder: FolderNode
  ): FolderNode[] => {
    return nodes.map(node => {
      if (node.key === parentKey) {
        return {
          ...node,
          children: [...(node.children || []), newFolder]
        }
      }
      if (node.children) {
        return {
          ...node,
          children: addToFolder(node.children, parentKey, newFolder)
        }
      }
      return node
    })
  }

  // 重命名文件夹
  const handleRenameSubmit = (key: string) => {
    if (!editingTitle.trim()) {
      message.error('文件夹名称不能为空')
      return
    }

    const updateFolder = (nodes: FolderNode[]): FolderNode[] => {
      return nodes.map(node => {
        if (node.key === key) {
          return { ...node, title: editingTitle }
        }
        if (node.children) {
          return { ...node, children: updateFolder(node.children) }
        }
        return node
      })
    }

    onUpdate(updateFolder(folders))
    setEditingKey(null)
    setEditingTitle('')
    message.success('重命名成功')
  }

  // 删除文件夹
  const handleDeleteFolder = (key: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个文件夹吗？文件夹内的文件不会被删除，将移动到根目录。',
      okText: '删除',
      cancelText: '取消',
      onOk: () => {
        const removeFolder = (nodes: FolderNode[]): FolderNode[] => {
          return nodes
            .filter(node => node.key !== key)
            .map(node => {
              if (node.children) {
                return { ...node, children: removeFolder(node.children) }
              }
              return node
            })
        }

        onUpdate(removeFolder(folders))
        if (selectedFolder === key) {
          onSelect('root')
        }
        message.success('文件夹已删除')
      }
    })
  }

  // 右键菜单
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
    {
      type: 'divider' as const
    },
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
