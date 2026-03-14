import { Menu } from 'antd'
import {
  FileTextOutlined,
  EditOutlined,
  ExpandOutlined,
  CompressOutlined,
  SearchOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'

/**
 * 右键菜单组件
 * 提供AI辅助功能的快捷入口
 */

interface ContextMenuProps {
  visible: boolean
  x: number
  y: number
  selectedText: string
  onMenuClick: (key: string) => void
  onClose: () => void
}

const ContextMenu: React.FC<ContextMenuProps> = ({
  visible,
  x,
  y,
  selectedText,
  onMenuClick,
  onClose
}) => {
  const { colors } = useTheme()

  if (!visible) return null

  // 菜单项配置
  const menuItems = [
    {
      key: 'generate-draft',
      icon: <FileTextOutlined />,
      label: '生成初稿',
      shortcut: 'Ctrl+Shift+G',
      disabled: !!selectedText // 有选中文本时禁用
    },
    { type: 'divider' },
    {
      key: 'rewrite',
      icon: <EditOutlined />,
      label: '改写此段',
      shortcut: 'Ctrl+Shift+R',
      disabled: !selectedText // 无选中文本时禁用
    },
    {
      key: 'expand',
      icon: <ExpandOutlined />,
      label: '扩写',
      shortcut: 'Ctrl+Shift+E',
      disabled: !selectedText
    },
    {
      key: 'simplify',
      icon: <CompressOutlined />,
      label: '精简',
      shortcut: 'Ctrl+Shift+C',
      disabled: !selectedText
    },
    { type: 'divider' },
    {
      key: 'search',
      icon: <SearchOutlined />,
      label: '综合检索',
      shortcut: 'Ctrl+Shift+S',
      disabled: !selectedText
    },
    {
      key: 'ask',
      icon: <QuestionCircleOutlined />,
      label: '提问',
      shortcut: 'Ctrl+Shift+Q'
    }
  ]

  const handleClick = ({ key }: { key: string }) => {
    onMenuClick(key)
    onClose()
  }

  // 点击外部关闭菜单
  const handleClickOutside = () => {
    onClose()
  }

  return (
    <>
      {/* 遮罩层 - 点击关闭菜单 */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 999
        }}
        onClick={handleClickOutside}
        onContextMenu={(e) => {
          e.preventDefault()
          handleClickOutside()
        }}
      />

      {/* 菜单 */}
      <div
        style={{
          position: 'fixed',
          top: y,
          left: x,
          zIndex: 1000,
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.borderColor}`,
          borderRadius: 8,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
          minWidth: 200
        }}
      >
        <Menu
          mode="vertical"
          onClick={handleClick}
          style={{
            backgroundColor: colors.bgSecondary,
            border: 'none'
          }}
          items={menuItems.map(item => {
            if (item.type === 'divider') {
              return { type: 'divider' as const }
            }
            return {
              key: item.key,
              icon: item.icon,
              disabled: item.disabled,
              label: (
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  color: item.disabled ? colors.textSecondary : colors.textPrimary
                }}>
                  <span>{item.label}</span>
                  <span style={{
                    fontSize: 12,
                    color: colors.textSecondary,
                    marginLeft: 24
                  }}>
                    {item.shortcut}
                  </span>
                </div>
              )
            }
          })}
        />
      </div>
    </>
  )
}

export default ContextMenu
