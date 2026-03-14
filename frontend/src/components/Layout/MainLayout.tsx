import { Layout, Menu, Switch, Space } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  CloudUploadOutlined,
  RobotOutlined,
  DatabaseOutlined,
  SettingOutlined,
  BulbOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useTheme } from '../../contexts/ThemeContext'

const { Header, Content } = Layout

interface MainLayoutProps {
  children: React.ReactNode
}

/**
 * 主布局组件
 * 顶部横向菜单栏布局
 */
const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { colors, theme, toggleTheme } = useTheme()

  // 菜单项配置（简化为4个主界面）
  const menuItems: MenuProps['items'] = [
    {
      key: '/upload',
      icon: <CloudUploadOutlined />,
      label: '文档上传',
    },
    {
      key: '/ai-creation',
      icon: <RobotOutlined />,
      label: 'AI编辑',
    },
    {
      key: '/library',
      icon: <DatabaseOutlined />,
      label: '库管理',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ]

  // 菜单点击处理
  const handleMenuClick: MenuProps['onClick'] = (e) => {
    navigate(e.key)
  }

  // 获取当前选中的菜单项
  const getSelectedKey = () => {
    const path = location.pathname
    if (path.startsWith('/upload')) return '/upload'
    if (path.startsWith('/ai-creation')) return '/ai-creation'
    if (path.startsWith('/library')) return '/library'
    if (path.startsWith('/settings')) return '/settings'
    return path
  }

  return (
    <Layout style={{ minHeight: '100vh', backgroundColor: colors.bgPrimary }}>
      {/* 顶部导航栏 */}
      <Header style={{ 
        background: colors.bgSecondary, 
        color: colors.textPrimary, 
        padding: '0 24px',
        borderBottom: `1px solid ${colors.borderColor}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        height: '64px',
        lineHeight: '64px'
      }}>
        {/* 左侧：系统标题 */}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h1 style={{ 
            color: colors.textPrimary, 
            margin: 0, 
            fontSize: '20px',
            marginRight: '48px',
            fontWeight: 600
          }}>
            工艺文件辅助编辑系统
          </h1>
          
          {/* 横向菜单 */}
          <Menu
            mode="horizontal"
            selectedKeys={[getSelectedKey()]}
            items={menuItems}
            onClick={handleMenuClick}
            style={{ 
              flex: 1,
              backgroundColor: 'transparent',
              border: 'none',
              lineHeight: '64px'
            }}
            theme={theme === 'dark' ? 'dark' : 'light'}
          />
        </div>

        {/* 右侧：主题切换 */}
        <Space>
          <BulbOutlined style={{ color: colors.textSecondary }} />
          <Switch 
            checked={theme === 'dark'} 
            onChange={toggleTheme}
            checkedChildren="黑"
            unCheckedChildren="白"
          />
        </Space>
      </Header>

      {/* 内容区域 */}
      <Layout style={{ backgroundColor: colors.bgPrimary }}>
        <Content
          style={{
            background: colors.bgPrimary,
            minHeight: 'calc(100vh - 64px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
