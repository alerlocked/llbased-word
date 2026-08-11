/**
 * MarkdownTiptapEditor - 基于 Tiptap 的 Markdown 编辑器
 * 支持内联图片，类似 Word 的编辑体验
 * 集成 AI 功能：选区快捷菜单 + 底部建议栏
 */
import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Image from '@tiptap/extension-image'
import { markdownToHtml, htmlToMarkdown } from '../../utils/markdownConverter'
import AISuggestionBar from '../editor/AISuggestionBar'
import { useSelection } from '../../hooks/useSelection'
import { useAIStream } from '../../hooks/useAIStream'
import { message } from 'antd'

interface MarkdownTiptapEditorProps {
  value: string // Markdown 格式的内容
  onChange: (markdown: string) => void // 返回 Markdown 格式
  placeholder?: string
  disabled?: boolean
  style?: React.CSSProperties
  onFocus?: () => void
  onBlur?: () => void
  editorRef?: React.RefObject<any>
  enableAI?: boolean // 是否启用 AI 功能，默认 true
  onOpenImageDialog?: () => void // 打开图片对话框的回调
  onPasteToChat?: (text: string) => void // 选区"贴入"到对话框的回调
}

const MarkdownTiptapEditor = React.forwardRef<any, MarkdownTiptapEditorProps>(({
  value,
  onChange,
  placeholder = '选中文字后点贴入送给 AI 助手',
  disabled = false,
  style,
  onFocus,
  onBlur,
  editorRef: externalRef,
  enableAI = true,
  onOpenImageDialog,
  onPasteToChat,
}, ref) => {
  const internalEditorRef = useRef<any>(null)
  const editorRefForSelection = useRef<any>(null)
  
  // AI 功能状态
  const [aiSuggestionBarVisible, setAiSuggestionBarVisible] = useState(true)

  // 初始化 Tiptap 编辑器
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3]
        }
      }),
      Placeholder.configure({
        placeholder
      }),
      Image.configure({
        inline: true,
        allowBase64: true,
        HTMLAttributes: {
          class: 'inline-image',
          loading: 'lazy',
          onerror: `this.onerror=null; this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'200\\' height=\\'200\\'%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\' dy=\\'.3em\\' fill=\\'%23999\\'%3E图片加载失败%3C/text%3E%3C/svg%3E';`
        }
      }).extend({
        addAttributes() {
          return {
            ...this.parent?.(),
            src: {
              default: null,
              parseHTML: (element: HTMLElement) => {
                const src = element.getAttribute('src')
                console.log('[Tiptap Image parseHTML] 原始src:', src)
                
                if (!src) return null
                
                if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('data:')) {
                  if (src.includes('localhost:3000')) {
                    let correctedSrc = src.replace('localhost:3000', 'localhost:8000')
                    correctedSrc = correctedSrc.replace(/ /g, '_')
                    console.log('[Tiptap Image parseHTML] 修正端口:3000->8000，处理空格:', correctedSrc)
                    return correctedSrc
                  }
                  console.log('[Tiptap Image parseHTML] 完整URL，直接返回')
                  return src
                }
                
                let normalizedSrc = src.trim().replace(/^["']|["']$/g, '')
                if (!normalizedSrc.startsWith('/')) {
                  normalizedSrc = '/' + normalizedSrc
                }
                normalizedSrc = normalizedSrc.replace(/\/+/g, '/')
                
                const fullUrl = `http://localhost:8000${normalizedSrc}`
                console.log('[Tiptap Image parseHTML] 转换后的URL:', fullUrl)
                return fullUrl
              },
              renderHTML: (attributes: any) => {
                if (!attributes.src) return {}
                return { src: attributes.src }
              }
            }
          }
        }
      })
    ],
    content: markdownToHtml(value || ''),
    editable: !disabled,
    onUpdate: ({ editor }) => {
      if (isUpdatingRef.current) return
      
      const html = editor.getHTML()
      const markdown = htmlToMarkdown(html)
      
      lastValueRef.current = markdown
      
      onChange(markdown)
    },
    onFocus,
    onBlur,
    editorProps: {
      attributes: {
        class: 'markdown-tiptap-editor',
        style: `
          min-height: calc(100vh - 160px);
          padding: 16px;
          outline: none;
          font-family: "Noto Serif SC", "Source Han Serif CN", Georgia, serif;
          font-size: 16px;
          line-height: 1.9;
          letter-spacing: 0.02em;
        `
      }
    }
  })

  // 同步编辑器 ref
  useEffect(() => {
    if (ref) {
      if (typeof ref === 'function') {
        ref(editor)
      } else if ('current' in ref) {
        (ref as React.MutableRefObject<any>).current = editor
      }
    }
    if (externalRef && 'current' in externalRef) {
      (externalRef as React.MutableRefObject<any>).current = editor
    }
    internalEditorRef.current = editor
    editorRefForSelection.current = editor
  }, [editor, ref, externalRef])

  // 选区检测 Hook（在 editor 准备好后才使用）
  const { selection, position, isVisible: isMenuVisible } = useSelection(
    enableAI && editor ? editor : null
  )
  
  // AI 流式生成 Hook（用于建议栏）
  const {
    state: aiState,
    content: aiContent,
    startStream: startAIStream,
    cancelStream: cancelAIStream,
  } = useAIStream({
    maxRetries: 3,
    onComplete: (content) => {
      // 建议栏点击后的内容插入到光标位置
      if (editor && content) {
        editor
          .chain()
          .focus()
          .insertContent(content)
          .run()
      }
    },
  })

  const lastValueRef = useRef<string>(value || '')
  const isUpdatingRef = useRef(false)

  // 当外部 value 变化时更新编辑器内容
  useEffect(() => {
    if (!editor) return
    
    if (isUpdatingRef.current) {
      console.log('[MarkdownTiptapEditor] 正在更新中，跳过外部value变化')
      return
    }
    
    const currentValue = value || ''
    const lastValue = lastValueRef.current
    
    if (currentValue === lastValue) {
      console.log('[MarkdownTiptapEditor] value未变化，跳过')
      return
    }
    
    const currentHtml = editor.getHTML()
    const currentMarkdown = htmlToMarkdown(currentHtml)
    
    const normalizedCurrent = currentMarkdown.trim()
    const normalizedValue = currentValue.trim()
    
    console.log('[MarkdownTiptapEditor] 外部value变化，当前编辑器内容长度:', normalizedCurrent.length, '新value长度:', normalizedValue.length)
    
    if (normalizedCurrent !== normalizedValue) {
      console.log('[MarkdownTiptapEditor] 内容不同，将更新编辑器！')
      isUpdatingRef.current = true
      const newHtml = markdownToHtml(currentValue)
      
      editor.commands.setContent(newHtml, false)
      
      lastValueRef.current = currentValue
      
      setTimeout(() => {
        isUpdatingRef.current = false
      }, 0)
    } else {
      console.log('[MarkdownTiptapEditor] 内容相同（仅空白字符差异），只更新ref')
      lastValueRef.current = currentValue
    }
  }, [value, editor])
  
  // 编辑器创建后，初始化 lastValueRef
  useEffect(() => {
    if (editor) {
      const initialMarkdown = value || ''
      lastValueRef.current = initialMarkdown
      
      const currentHtml = editor.getHTML()
      const currentMarkdown = htmlToMarkdown(currentHtml)
      if (currentMarkdown.trim() !== initialMarkdown.trim()) {
        isUpdatingRef.current = true
        editor.commands.setContent(markdownToHtml(initialMarkdown), false)
        setTimeout(() => {
          isUpdatingRef.current = false
        }, 0)
      }
    }
  }, [editor])

  // AI 建议栏操作
  const handleSuggestionAction = useCallback((action: string) => {
    if (!editor) return
    
    // 检查编辑器是否有内容
    const isEmpty = editor.state.doc.textContent.trim().length === 0
    if (isEmpty) {
      message.warning('请先输入内容后再使用 AI 功能')
      return
    }
    
    // 获取当前光标位置的上下文
    const { $from } = editor.state.selection
    const start = Math.max(0, $from.pos - 200)
    const end = Math.min(editor.state.doc.content.size, $from.pos + 200)
    
    let context = ''
    try {
      context = editor.state.doc.textBetween(start, end)
    } catch (e) {
      // 忽略错误
    }
    
    // 启动 AI 流式生成
    startAIStream(action, '', context)
  }, [editor, startAIStream])

  if (!editor) {
    return <div>加载编辑器...</div>
  }

  return (
    <div style={{ position: 'relative', width: '100%', ...style }}>
      <EditorContent editor={editor} />
      
      {/* AI 选区"贴入"浮按钮 — 选中文字后浮出，点击把选区送给对话框（Cursor 式并入对话） */}
      {enableAI && isMenuVisible && selection?.text && onPasteToChat && position && (
        <button
          type="button"
          onClick={() => {
            onPasteToChat(selection.text)
          }}
          style={{
            position: 'fixed',
            top: Math.max(8, position.top - 44),
            left: position.left,
            zIndex: 1000,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '6px 12px',
            fontSize: 13,
            color: '#fff',
            background: '#1890ff',
            border: 'none',
            borderRadius: 6,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
          title="把选中的文字作为引用送给 AI 助手"
        >
          📎 贴入送给 AI
        </button>
      )}
      
      {/* AI 底部建议栏 */}
      {enableAI && (
        <AISuggestionBar
          editor={editor}
          onAction={handleSuggestionAction}
          visible={aiSuggestionBarVisible}
        />
      )}
      
      <style>{`
        .markdown-tiptap-editor {
          color: inherit;
        }
        .markdown-tiptap-editor p {
          margin-bottom: 1em;
        }
        .markdown-tiptap-editor p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: #adb5bd;
          pointer-events: none;
          height: 0;
        }
        .markdown-tiptap-editor .inline-image {
          cursor: pointer;
          user-select: none;
          display: inline-block;
          vertical-align: middle;
          margin: 4px 0;
          max-width: 100%;
          height: auto;
          border-radius: 4px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .markdown-tiptap-editor .inline-image.ProseMirror-selectednode {
          outline: 2px solid #1890ff;
          outline-offset: 2px;
        }
        .markdown-tiptap-editor img {
          max-width: 100%;
          height: auto;
          display: block;
        }
      `}</style>
    </div>
  )
})

MarkdownTiptapEditor.displayName = 'MarkdownTiptapEditor'

export default MarkdownTiptapEditor
