import React, { useState, useEffect } from 'react'
import { Modal, Tabs, Input, Button, List, Card, Image, Empty, Spin, message, Space, Radio } from 'antd'
import { SearchOutlined, PictureOutlined, CloudDownloadOutlined, FileImageOutlined } from '@ant-design/icons'

interface ImageResult {
  type: string
  url: string
  original_url?: string  // 原始URL（用于未下载的图片）
  thumbnail: string
  title: string
  source: string
  id: number | null
  is_downloaded?: boolean  // 是否已下载
}

interface ImageInsertDialogProps {
  projectId: number | null
  visible: boolean
  onCancel: () => void
  onInsert: (markdown: string) => void
}

const ImageInsertDialog: React.FC<ImageInsertDialogProps> = ({
  projectId,
  visible,
  onCancel,
  onInsert
}) => {
  const [activeTab, setActiveTab] = useState('local')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<ImageResult[]>([])
  const [searched, setSearched] = useState(false)

  // 自动搜索（当切换tab或打开时，如果是本地且无query，可以列出默认）
  useEffect(() => {
    if (visible && projectId) {
      if (activeTab === 'local' && !searched) {
        handleSearch(true) // 默认加载本地图片
      }
    } else if (!visible) {
        // 重置状态
        setQuery('')
        setResults([])
        setSearched(false)
    }
  }, [visible, activeTab, projectId])

  const handleSearch = async (isInitial = false) => {
    if (!projectId) return
    // 如果是初始加载本地，不需要query。如果是网络搜索，必须有query。
    if (activeTab === 'web' && !query.trim()) {
        if (!isInitial) message.warning('请输入搜索词')
        return
    }

    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/images/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          source: activeTab // 'local' or 'web'
        })
      })

      if (response.ok) {
        const data = await response.json()
        setResults(data)
        setSearched(true)
      } else {
        message.error('搜索失败')
      }
    } catch (error) {
      console.error('搜索图片失败:', error)
      message.error('网络错误')
    } finally {
      setLoading(false)
    }
  }

  const handleInsert = async (img: ImageResult) => {
    // 如果是未下载的网络图片，先下载
    if (img.type === 'web' && !img.is_downloaded && img.original_url && projectId) {
      try {
        message.loading({ content: '正在下载图片...', key: 'download' })
        const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/images/download`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: img.original_url,
            keyword: img.title
          })
        })
        
        if (response.ok) {
          const data = await response.json()
          message.success({ content: '图片下载成功', key: 'download' })
          // 使用下载后的本地URL（去掉后端地址，使用相对路径）
          let imageUrl = data.url
          if (imageUrl.startsWith('http://localhost:8000')) {
            imageUrl = imageUrl.replace('http://localhost:8000', '')
          }
          // 清理 alt 文本中的特殊字符，避免 Markdown 语法错误
          let altText = (img.title || '图片').replace(/[\[\]()]/g, '').trim()
          if (!altText) {
            altText = '图片'
          }
          const markdown = `![${altText}](${imageUrl})`
          onInsert(markdown)
          onCancel()
        } else {
          message.error({ content: '图片下载失败', key: 'download' })
          // 下载失败，使用原始URL（完整URL）
          let altText = (img.title || '图片').replace(/[\[\]()]/g, '').trim()
          if (!altText) {
            altText = '图片'
          }
          const markdown = `![${altText}](${img.url})`
          onInsert(markdown)
          onCancel()
        }
      } catch (error) {
        console.error('下载图片失败:', error)
        message.error({ content: '网络错误', key: 'download' })
        // 出错时使用原始URL
        let altText = (img.title || '图片').replace(/[\[\]()]/g, '').trim()
        if (!altText) {
          altText = '图片'
        }
        const markdown = `![${altText}](${img.url})`
        onInsert(markdown)
        onCancel()
      }
    } else {
      // 已下载或本地图片，直接使用URL
      // 注意：插入时使用相对路径，MarkdownRenderer会自动处理URL
      // 如果URL已经是完整URL（网络图片），直接使用；否则使用相对路径
      let finalUrl = img.url
      
      // 如果是完整URL（网络图片），直接使用
      // 如果是相对路径（本地图片），也直接使用，MarkdownRenderer会处理
      // 确保URL格式正确
      if (finalUrl.startsWith('http://localhost:8000')) {
        // 如果已经包含后端地址，去掉它，使用相对路径
        finalUrl = finalUrl.replace('http://localhost:8000', '')
      }
      
      // 确保alt文本不为空，并清理特殊字符（避免Markdown语法错误）
      let altText = (img.title || '图片').replace(/[\[\]()]/g, '')
      if (!altText.trim()) {
        altText = '图片'
      }
      
      // 构建Markdown格式，确保格式正确
      const markdown = `![${altText}](${finalUrl})`
      onInsert(markdown)
      onCancel()
    }
  }

  const renderResultList = () => {
    if (loading) {
      return <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="搜索中..." /></div>
    }

    if (results.length === 0 && searched) {
      return <Empty description="未找到相关图片" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    }

    if (results.length === 0 && !searched) {
        return <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>请输入关键词进行搜索</div>
    }

    return (
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', 
        gap: 16,
        maxHeight: 400,
        overflowY: 'auto',
        padding: 4
      }}>
        {results.map((img, idx) => (
          <div 
            key={idx} 
            style={{ 
              border: '1px solid #f0f0f0', 
              borderRadius: 8, 
              overflow: 'hidden',
              cursor: 'pointer',
              transition: 'all 0.2s',
              position: 'relative'
            }}
            onClick={() => handleInsert(img)}
            className="image-card"
          >
            <div style={{ height: 100, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5' }}>
               <img 
                 src={(() => {
                   // 处理图片URL：如果是完整URL直接使用，否则拼接后端地址
                   const thumbnail = img.thumbnail || img.url
                   if (thumbnail.startsWith('http://') || thumbnail.startsWith('https://')) {
                     return thumbnail
                   }
                   return `http://localhost:8000${thumbnail}`
                 })()} 
                 alt={img.title} 
                 style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'cover' }} 
                 onError={(e) => {
                   // 如果加载失败，尝试使用原始URL
                   const target = e.target as HTMLImageElement
                   const originalUrl = img.url
                   if (originalUrl && originalUrl !== target.src) {
                     if (originalUrl.startsWith('http://') || originalUrl.startsWith('https://')) {
                       target.src = originalUrl
                     } else {
                       target.src = `http://localhost:8000${originalUrl}`
                     }
                   }
                 }}
               />
            </div>
            <div style={{ padding: 8, fontSize: 12 }}>
              <div style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={img.title}>
                {img.title}
              </div>
              <div style={{ color: '#999', fontSize: 10, display: 'flex', justifyContent: 'space-between' }}>
                <span>{img.source}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <Modal
      title="插入图片"
      open={visible}
      onCancel={onCancel}
      footer={null}
      width={640}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'local',
            label: <span><FileImageOutlined /> 本地图库</span>,
            children: (
              <div>
                <div style={{ display: 'flex', marginBottom: 16 }}>
                  <Input 
                    placeholder="搜索文档图片或已下载素材..." 
                    value={query} 
                    onChange={e => setQuery(e.target.value)}
                    onPressEnter={() => handleSearch()}
                    allowClear
                  />
                  <Button type="primary" icon={<SearchOutlined />} onClick={() => handleSearch()} style={{ marginLeft: 8 }}>
                    搜索
                  </Button>
                </div>
                {renderResultList()}
              </div>
            )
          },
          {
            key: 'web',
            label: <span><CloudDownloadOutlined /> 网络素材</span>,
            children: (
              <div>
                <div style={{ display: 'flex', marginBottom: 16 }}>
                  <Input 
                    placeholder="输入关键词搜索网络图片..." 
                    value={query} 
                    onChange={e => setQuery(e.target.value)}
                    onPressEnter={() => handleSearch()}
                    allowClear
                  />
                  <Button type="primary" icon={<SearchOutlined />} onClick={() => handleSearch()} style={{ marginLeft: 8 }}>
                    搜索
                  </Button>
                </div>
                {renderResultList()}
              </div>
            )
          }
        ]}
      />
    </Modal>
  )
}

export default ImageInsertDialog

