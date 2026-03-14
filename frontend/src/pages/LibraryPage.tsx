/**
 * LibraryPage - 统一的库管理页面
 * 合并知识库和风格文章库管理
 */
import { useState } from 'react'
import { Tabs } from 'antd'
import { DatabaseOutlined, BookOutlined } from '@ant-design/icons'
import MainLayout from '../components/Layout/MainLayout'

// 导入原有的两个库管理组件的核心内容
import KnowledgeBaseTab from '../components/Library/KnowledgeBaseTab'
import StyleLibraryTab from '../components/Library/StyleLibraryTab'

const LibraryPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('knowledge')

  return (
    <MainLayout>
      <div style={{ padding: '24px', maxWidth: 1600, margin: '0 auto' }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          size="large"
          tabBarStyle={{ marginBottom: 24 }}
          items={[
            {
              key: 'knowledge',
              label: (
                <span>
                  <DatabaseOutlined />
                  知识库
                </span>
              ),
              children: <KnowledgeBaseTab />
            },
            {
              key: 'style',
              label: (
                <span>
                  <BookOutlined />
                  风格文章库
                </span>
              ),
              children: <StyleLibraryTab />
            }
          ]}
        />
      </div>
    </MainLayout>
  )
}

export default LibraryPage

