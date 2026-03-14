import { useState } from 'react'
import { Modal, Input, Select, Button, Space, Typography } from 'antd'
import { useTheme } from '../../contexts/ThemeContext'

const { TextArea } = Input
const { Option } = Select
const { Text } = Typography

/**
 * AI对话框组件
 * 用于生成初稿、综合检索、提问等功能
 */

export type AIDialogType = 'draft' | 'search' | 'ask' | 'rewrite' | 'expand' | 'simplify'

interface AIDialogProps {
  open: boolean
  type: AIDialogType
  initialContent?: string
  onClose: () => void
  onConfirm: (params: any) => Promise<void>
}

const AIDialog: React.FC<AIDialogProps> = ({
  open,
  type,
  initialContent = '',
  onClose,
  onConfirm
}) => {
  const { colors } = useTheme()
  const [loading, setLoading] = useState(false)
  
  // 生成初稿参数
  const [outline, setOutline] = useState('')
  const [style, setStyle] = useState('news')
  const [wordCount, setWordCount] = useState(1000)
  
  // 提问参数
  const [question, setQuestion] = useState('')
  
  // 检索参数
  const [searchText, setSearchText] = useState(initialContent)

  /**
   * 获取对话框标题
   */
  const getTitle = () => {
    const titles = {
      draft: '生成初稿',
      search: '综合检索',
      ask: '提问',
      rewrite: '改写此段',
      expand: '扩写',
      simplify: '精简'
    }
    return titles[type]
  }

  /**
   * 处理确认
   */
  const handleConfirm = async () => {
    setLoading(true)
    try {
      let params: any = {}
      
      switch (type) {
        case 'draft':
          params = { outline, style, word_count: wordCount }
          break
        case 'ask':
          params = { question, context: initialContent }
          break
        case 'search':
          params = { query_text: searchText }
          break
        case 'rewrite':
        case 'expand':
        case 'simplify':
          params = { text: initialContent, operation: type }
          break
      }
      
      await onConfirm(params)
      onClose()
    } catch (error) {
      console.error('AI操作失败:', error)
    } finally {
      setLoading(false)
    }
  }

  /**
   * 渲染对话框内容
   */
  const renderContent = () => {
    switch (type) {
      case 'draft':
        return (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              <Text strong>大纲/主题/思想:</Text>
              <TextArea
                rows={6}
                value={outline}
                onChange={(e) => setOutline(e.target.value)}
                placeholder="请输入大纲、主题或核心思想..."
                style={{ marginTop: 8 }}
              />
            </div>
            <div>
              <Text strong>文风:</Text>
              <Select
                value={style}
                onChange={setStyle}
                style={{ width: '100%', marginTop: 8 }}
              >
                <Option value="standard">标准</Option>
                <Option value="detailed">详细</Option>
                <Option value="comment">评论</Option>
                <Option value="report">报道</Option>
              </Select>
            </div>
            <div>
              <Text strong>字数要求:</Text>
              <Input
                type="number"
                value={wordCount}
                onChange={(e) => setWordCount(parseInt(e.target.value) || 1000)}
                style={{ marginTop: 8 }}
                addonAfter="字"
              />
            </div>
          </Space>
        )
      
      case 'ask':
        return (
          <div>
            <Text strong>您的问题:</Text>
            <TextArea
              rows={4}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="请输入您的问题..."
              style={{ marginTop: 8 }}
            />
            {initialContent && (
              <div style={{ marginTop: 16 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  上下文: {initialContent.substring(0, 100)}...
                </Text>
              </div>
            )}
          </div>
        )
      
      case 'search':
        return (
          <div>
            <Text strong>检索内容:</Text>
            <TextArea
              rows={4}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="请输入要检索的内容..."
              style={{ marginTop: 8 }}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              将自动从内容、地理、历史、政治、经济等角度分析并检索
            </Text>
          </div>
        )
      
      case 'rewrite':
      case 'expand':
      case 'simplify':
        return (
          <div>
            <Text strong>待处理内容:</Text>
            <TextArea
              rows={6}
              value={initialContent}
              readOnly
              style={{ marginTop: 8 }}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              {type === 'rewrite' && '将改写选中的内容'}
              {type === 'expand' && '将扩写选中的内容'}
              {type === 'simplify' && '将精简选中的内容'}
            </Text>
          </div>
        )
      
      default:
        return null
    }
  }

  return (
    <Modal
      title={getTitle()}
      open={open}
      onCancel={onClose}
      onOk={handleConfirm}
      confirmLoading={loading}
      width={600}
      okText="确认"
      cancelText="取消"
    >
      {renderContent()}
    </Modal>
  )
}

export default AIDialog

