import { useEffect, useRef, useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Statistic, Space, Upload, Button, message } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'
import { draftApi } from '../../services/draftApi'
import ExportButton from './ExportButton'

/**
 * 编辑器面板组件
 * 使用Tiptap实现基础文本编辑功能,支持拖拽、右键菜单、自动保存
 */

interface EditorPanelProps {
  content: string
  onChange: (content: string) => void
  onContextMenu?: (event: React.MouseEvent, selectedText: string) => void
  placeholder?: string
  projectId?: number
}

const EditorPanel: React.FC<EditorPanelProps> = ({ 
  content, 
  onChange, 
  onContextMenu,
  placeholder = '开始撰写...',
  projectId
}) => {
  const { colors } = useTheme()
  const editorRef = useRef<HTMLDivElement>(null)
  const autoSaveTimerRef = useRef<NodeJS.Timeout>()
  const [currentDraftId, setCurrentDraftId] = useState<number | undefined>(undefined)
  const [uploading, setUploading] = useState(false)

  /**
   * 初始化编辑器
   */
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // 禁用不需要的功能,保持简洁
        heading: {
          levels: [1, 2, 3]
        }
      }),
      Placeholder.configure({
        placeholder
      })
    ],
    content,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML()
      onChange(html)
      
      // 自动保存 - 3秒后保存
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }
      autoSaveTimerRef.current = setTimeout(() => {
        autoSave(html)
      }, 3000)
    },
    editorProps: {
      attributes: {
        class: 'tiptap-editor',
        style: `
          min-height: 100%;
          padding: 24px;
          outline: none;
          color: ${colors.textPrimary};
          background-color: ${colors.bgPrimary};
          line-height: 1.8;
          font-size: 16px;
        `
      },
      // 处理拖拽放置
      handleDrop: (view, event, slice, moved) => {
        // 检查是否有自定义数据
        const jsonData = event.dataTransfer?.getData('application/json')
        if (jsonData) {
          try {
            const data = JSON.parse(jsonData)
            if (data.type === 'segment') {
              // 插入段落文本
              const { tr } = view.state
              const pos = view.posAtCoords({ left: event.clientX, top: event.clientY })
              if (pos) {
                tr.insertText(data.data.text, pos.pos)
                view.dispatch(tr)
                return true
              }
            }
          } catch (e) {
            console.error('解析拖拽数据失败:', e)
          }
        }
        return false
      }
    }
  })

  /**
   * 自动保存
   */
  const autoSave = async (html: string) => {
    if (!projectId) return
    
    try {
      // 保存到localStorage作为草稿
      localStorage.setItem(`draft_${projectId}`, html)
      console.log('✅ 草稿已自动保存')
    } catch (error) {
      console.error('❌ 自动保存失败:', error)
    }
  }

  /**
   * 上传初稿文件
   */
  const handleUploadDraft = async (file: File) => {
    setUploading(true)
    try {
      const result = await draftApi.uploadDraft(file, projectId)
      setCurrentDraftId(result.id)
      // 将解析内容加载到编辑器
      if (editor && result.content) {
        editor.commands.setContent(result.content)
      }
      message.success(`初稿「${result.title}」上传成功`)
    } catch (error) {
      console.error('上传初稿失败:', error)
    } finally {
      setUploading(false)
    }
    // 阻止 antd Upload 默认上传行为
    return false
  }

  /**
   * 处理右键菜单
   */
  const handleContextMenu = (e: React.MouseEvent) => {
    if (!editor || !onContextMenu) return
    
    e.preventDefault()
    const selectedText = editor.state.doc.textBetween(
      editor.state.selection.from,
      editor.state.selection.to
    )
    onContextMenu(e, selectedText)
  }

  /**
   * 计算字数
   */
  const getWordCount = () => {
    if (!editor) return 0
    const text = editor.getText()
    // 中文字符 + 英文单词
    const chineseChars = text.match(/[\u4e00-\u9fa5]/g)?.length || 0
    const englishWords = text.match(/[a-zA-Z]+/g)?.length || 0
    return chineseChars + englishWords
  }

  // 清理定时器
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }
    }
  }, [])

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: colors.bgPrimary,
        overflow: 'hidden'
      }}
    >
      {/* 工具栏 - 字数统计 + 上传 + 导出 */}
      <div style={{
        padding: '12px 24px',
        borderBottom: `1px solid ${colors.borderColor}`,
        backgroundColor: colors.bgSecondary,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <Space>
          <Statistic 
            title="字数" 
            value={getWordCount()} 
            valueStyle={{ fontSize: 16, color: colors.textPrimary }}
          />
          <Upload
            accept=".pdf"
            showUploadList={false}
            beforeUpload={(file) => { handleUploadDraft(file); return false }}
          >
            <Button
              icon={<UploadOutlined />}
              loading={uploading}
              size="small"
            >
              上传初稿
            </Button>
          </Upload>
        </Space>
        <Space>
          <ExportButton draftId={currentDraftId} projectId={projectId} />
        </Space>
      </div>

      {/* 编辑器 */}
      <div
        ref={editorRef}
        onContextMenu={handleContextMenu}
        style={{ flex: 1, overflow: 'hidden' }}
      >
        <EditorContent editor={editor} />
      </div>

      <style>{`
        .tiptap-editor {
          flex: 1;
          overflow-y: auto;
        }
        .tiptap-editor p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: ${colors.textSecondary};
          pointer-events: none;
          height: 0;
        }
        .tiptap-editor h1 {
          font-size: 2em;
          font-weight: bold;
          margin: 0.67em 0;
        }
        .tiptap-editor h2 {
          font-size: 1.5em;
          font-weight: bold;
          margin: 0.75em 0;
        }
        .tiptap-editor h3 {
          font-size: 1.17em;
          font-weight: bold;
          margin: 0.83em 0;
        }
        .tiptap-editor p {
          margin: 1em 0;
        }
        .tiptap-editor strong {
          font-weight: bold;
        }
        .tiptap-editor em {
          font-style: italic;
        }
        .tiptap-editor ul, .tiptap-editor ol {
          padding-left: 2em;
          margin: 1em 0;
        }
        .tiptap-editor blockquote {
          border-left: 4px solid ${colors.borderColor};
          padding-left: 1em;
          margin: 1em 0;
          color: ${colors.textSecondary};
        }
      `}</style>
    </div>
  )
}

export default EditorPanel

