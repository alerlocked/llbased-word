/**
 * KnowledgeScopeSelector - 知识库范围选择器
 * 类似 Get 笔记的知识范围选择功能
 */
import { useState, useEffect } from 'react'
import { Checkbox, Collapse, Badge, Button, Tooltip, Space } from 'antd'
import {
  DatabaseOutlined,
  FolderOutlined,
  CheckCircleOutlined,
  SettingOutlined
} from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

interface FolderScope {
  key: string
  title: string
  count?: number
  children?: FolderScope[]
}

interface KnowledgeScopeSelectorProps {
  folders: FolderScope[]
  selectedScopes: string[]
  onChange: (scopes: string[]) => void
  style?: React.CSSProperties
}

const STORAGE_KEY = 'knowledge_scope_selection'

const KnowledgeScopeSelector: React.FC<KnowledgeScopeSelectorProps> = ({
  folders,
  selectedScopes,
  onChange,
  style
}) => {
  const [expandedKeys, setExpandedKeys] = useState<string[]>(['root'])

  // 从 localStorage 加载保存的选择
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        onChange(parsed)
      } catch (e) {
        // 解析失败，使用默认值
      }
    }
  }, [])

  // 保存选择到 localStorage
  const saveSelection = (scopes: string[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(scopes))
  }

  // 处理选择变化
  const handleChange = (checkedValues: string[]) => {
    onChange(checkedValues)
    saveSelection(checkedValues)
  }

  // 全选/取消全选
  const handleSelectAll = () => {
    const allKeys = getAllFolderKeys(folders)
    onChange(allKeys)
    saveSelection(allKeys)
  }

  const handleClearAll = () => {
    onChange([])
    saveSelection([])
  }

  // 获取所有文件夹 key
  const getAllFolderKeys = (items: FolderScope[]): string[] => {
    const keys: string[] = []
    const traverse = (nodes: FolderScope[]) => {
      nodes.forEach(node => {
        keys.push(node.key)
        if (node.children) {
          traverse(node.children)
        }
      })
    }
    traverse(items)
    return keys
  }

  // 渲染文件夹选项
  const renderFolderOptions = (items: FolderScope[], level = 0): JSX.Element[] => {
    return items.flatMap(item => [
      <div
        key={item.key}
        style={{
          padding: '8px 12px',
          paddingLeft: 12 + level * 20,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}
      >
        <Checkbox
          value={item.key}
          style={{ transform: 'scale(0.9)' }}
        >
          <Space>
            <FolderOutlined style={{ color: colors.primary }} />
            <span>{item.title}</span>
            {item.count !== undefined && (
              <Badge
                count={item.count}
                style={{
                  backgroundColor: colors.bgTertiary,
                  color: colors.textSecondary,
                  fontSize: 10
                }}
              />
            )}
          </Space>
        </Checkbox>
      </div>,
      ...(item.children ? renderFolderOptions(item.children, level + 1) : [])
    ])
  }

  const selectedCount = selectedScopes.length
  const totalCount = getAllFolderKeys(folders).length

  return (
    <div style={{
      background: colors.bgSecondary,
      borderRadius: 8,
      padding: 12,
      ...style
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
        paddingBottom: 12,
        borderBottom: `1px solid ${colors.borderLight}`
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <DatabaseOutlined style={{ color: colors.primary }} />
          <span style={{ fontWeight: 500, color: colors.textPrimary }}>
            知识库范围
          </span>
          <Badge
            count={selectedCount}
            style={{
              backgroundColor: selectedCount > 0 ? colors.primary : colors.bgTertiary,
              color: selectedCount > 0 ? '#fff' : colors.textSecondary
            }}
          />
        </div>
        <Tooltip title="全选将检索所有知识库">
          <SettingOutlined style={{ color: colors.textTertiary, cursor: 'help' }} />
        </Tooltip>
      </div>

      <Checkbox.Group
        value={selectedScopes}
        onChange={handleChange as any}
        style={{ width: '100%' }}
      >
        {renderFolderOptions(folders)}
      </Checkbox.Group>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 12,
        paddingTop: 12,
        borderTop: `1px solid ${colors.borderLight}`
      }}>
        <Button
          type="link"
          size="small"
          onClick={handleSelectAll}
          style={{ padding: 0, color: colors.primary }}
        >
          全选
        </Button>
        <Button
          type="link"
          size="small"
          onClick={handleClearAll}
          style={{ padding: 0, color: colors.textSecondary }}
        >
          清空
        </Button>
      </div>

      {selectedCount > 0 && (
        <div style={{
          marginTop: 8,
          padding: '8px 12px',
          background: `${colors.primary}10`,
          borderRadius: 4,
          fontSize: 12,
          color: colors.textSecondary
        }}>
          <CheckCircleOutlined style={{ color: colors.primary, marginRight: 4 }} />
          AI 将从选中的 {selectedCount} 个知识库中检索信息
        </div>
      )}
    </div>
  )
}

export default KnowledgeScopeSelector
