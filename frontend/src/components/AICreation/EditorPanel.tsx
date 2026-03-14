/**
 * EditorPanel - 富文本编辑器面板
 * 支持文本编辑和引用管理
 */
import { useRef, useMemo } from 'react'
import { Button, Space, message } from 'antd'
import { SendOutlined, DownloadOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import * as diff from 'diff-match-patch'

// 兼容不同的导入方式
const { diff_match_patch, DIFF_DELETE, DIFF_INSERT } = (diff as any).default || diff

interface EditorPanelProps {
  content: string
  proposedContent?: string
  onChange: (content: string) => void
  onTextSelect: (text: string) => void
  onAccept: (newContent: string) => void
  onReject: () => void
  projectId?: number
}

const EditorPanel: React.FC<EditorPanelProps> = ({ 
  content, 
  proposedContent,
  onChange, 
  onTextSelect, 
  onAccept,
  onReject,
  projectId 
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const dmp = useMemo(() => new diff_match_patch(), [])

  // 计算最终建议的全量内容
  const fullProposedContent = useMemo(() => {
    if (!proposedContent) return ''
    if (!proposedContent.includes(content.slice(0, 20)) && content.length > 0) {
        return content + '\n\n' + proposedContent
    }
    return proposedContent
  }, [content, proposedContent])

  // 计算 Diff 渲染
  const diffElements = useMemo(() => {
    if (!proposedContent) return null
    
    const diffs = dmp.diff_main(content, fullProposedContent)
    dmp.diff_cleanupSemantic(diffs)
    
    return diffs.map(([type, text], index) => {
      const style: React.CSSProperties = {
        whiteSpace: 'pre-wrap',
        fontSize: 16,
        lineHeight: 1.8
      }
      
      if (type === DIFF_INSERT) {
        return <span key={index} style={{ ...style, backgroundColor: '#e6fffa', borderBottom: '2px solid #52c41a' }}>{text}</span>
      } else if (type === DIFF_DELETE) {
        return <span key={index} style={{ ...style, backgroundColor: '#fff1f0', textDecoration: 'line-through', color: '#ff4d4f' }}>{text}</span>
      }
      return <span key={index} style={style}>{text}</span>
    })
  }, [content, fullProposedContent, proposedContent, dmp])
  
  // 发送到AI的逻辑
  const handleSendToAI = () => {
    if (textareaRef.current) {
      const start = textareaRef.current.selectionStart
      const end = textareaRef.current.selectionEnd
      const selectedText = textareaRef.current.value.substring(start, end)
      
      if (selectedText) {
        onTextSelect(selectedText)
        message.success('已将选中文本发送至阿西莫夫')
      } else {
        message.info('请先用鼠标选取一段文字')
      }
    }
  }

  // 处理键盘快捷键
  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ctrl + Enter (or Cmd + Enter on Mac)
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSendToAI()
    }
  }

  // 确认落稿并导出Word
  const handleFinalizeAndExport = async () => {
    if (!projectId) {
      message.warning('请先选择或创建项目')
      return
    }

    try {
      message.loading('正在确认落稿并导出...', 0)
      
      // 1. 先保存到风格库
      const styleResponse = await fetch('http://localhost:8000/api/style/articles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `落稿_${new Date().toLocaleDateString()}_${projectId}`,
          content: content,
          user_id: 1 // TODO: 动态获取
        })
      })

      if (!styleResponse.ok) {
        throw new Error('保存到风格库失败')
      }

      // 2. 导出Word
      const exportResponse = await fetch('http://localhost:8000/api/export/word', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          include_annotations: true,
          include_citations: true,
          include_figures: true
        })
      })

      message.destroy()

      if (exportResponse.ok) {
        // 下载文件
        const blob = await exportResponse.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `article_${projectId}.docx`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        message.success('落稿成功并已导出Word')
      } else {
        message.error('导出Word失败，但已保存到风格库')
      }
    } catch (error) {
      message.destroy()
      console.error('操作失败:', error)
      message.error(error instanceof Error ? error.message : '操作失败')
    }
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 工具栏 */}
      <div style={{ 
        padding: '12px 16px', 
        borderBottom: '1px solid #f0f0f0',
        background: '#fafafa',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <Space>
          <Button
            size="small"
            icon={<SendOutlined />}
            onClick={handleSendToAI}
          >
            发送到AI
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            type="primary"
            onClick={handleFinalizeAndExport}
          >
            确认落稿并导出
          </Button>
        </Space>

        {proposedContent && (
          <Space>
            <span style={{ fontSize: 12, color: '#666' }}>AI 建议修改中：</span>
            <Button 
              size="small" 
              type="primary" 
              icon={<CheckOutlined />} 
              onClick={() => onAccept(fullProposedContent)}
              style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
            >
              接受修改
            </Button>
            <Button 
              size="small" 
              danger 
              icon={<CloseOutlined />} 
              onClick={onReject}
            >
              拒绝
            </Button>
          </Space>
        )}
      </div>

      {/* 编辑区域 */}
      <div style={{ flex: 1, padding: 16, overflow: 'auto', position: 'relative' }}>
        {proposedContent ? (
          <div style={{ padding: 12, border: '1px solid #d9d9d9', borderRadius: 4, background: '#fff', minHeight: '100%' }}>
            {diffElements}
          </div>
        ) : (
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="在此输入或编辑文章内容...&#10;&#10;提示：&#10;- 从左侧素材库点击添加素材&#10;- 选中文本后按 Ctrl+Enter 发送到右侧AI对话框&#10;- AI会自动在文中插入图片、注释和引用&#10;- 使用 Ctrl+S 快速保存"
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontSize: 16,
              lineHeight: 1.8,
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
            }}
          />
        )}
      </div>
    </div>
  )
}

export default EditorPanel
