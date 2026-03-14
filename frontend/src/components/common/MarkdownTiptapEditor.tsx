/**
 * MarkdownTiptapEditor - 基于 Tiptap 的 Markdown 编辑器
 * 支持内联图片，类似 Word 的编辑体验
 */
import React, { useEffect, useRef } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Image from '@tiptap/extension-image'
import { markdownToHtml, htmlToMarkdown } from '../../utils/markdownConverter'

interface MarkdownTiptapEditorProps {
  value: string // Markdown 格式的内容
  onChange: (markdown: string) => void // 返回 Markdown 格式
  placeholder?: string
  disabled?: boolean
  style?: React.CSSProperties
  onFocus?: () => void
  onBlur?: () => void
  editorRef?: React.RefObject<any>
}

const MarkdownTiptapEditor = React.forwardRef<any, MarkdownTiptapEditorProps>(({
  value,
  onChange,
  placeholder = '开始写作...',
  disabled = false,
  style,
  onFocus,
  onBlur,
  editorRef: externalRef
}, ref) => {
  const internalEditorRef = useRef<any>(null)

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
        inline: true, // 内联模式，图片作为行内元素
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
                
                // 如果已经是完整URL（http/https/data），需要检查是否是错误的端口
                if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('data:')) {
                  // 如果URL包含 localhost:3000，说明是错误的前端地址，需要替换为后端地址
                  if (src.includes('localhost:3000')) {
                    let correctedSrc = src.replace('localhost:3000', 'localhost:8000')
                    // 处理URL中的空格，替换为下划线
                    correctedSrc = correctedSrc.replace(/ /g, '_')
                    console.log('[Tiptap Image parseHTML] 修正端口:3000->8000，处理空格:', correctedSrc)
                    return correctedSrc
                  }
                  console.log('[Tiptap Image parseHTML] 完整URL，直接返回')
                  return src
                }
                
                // 相对路径，添加后端地址用于显示
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
                // 渲染时保持完整URL（包含localhost:8000），这样图片能正确显示
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
      // 如果正在从外部更新内容，跳过（避免循环）
      if (isUpdatingRef.current) return
      
      const html = editor.getHTML()
      const markdown = htmlToMarkdown(html)
      
      // 更新 lastValueRef，避免触发外部更新
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

  // 同步外部 ref
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
  }, [editor, ref, externalRef])

  // 使用 ref 跟踪上次的 value，避免循环更新
  const lastValueRef = useRef<string>(value || '')
  const isUpdatingRef = useRef(false)

  // 当外部 value 变化时更新编辑器内容（避免循环更新）
  useEffect(() => {
    if (!editor) return
    
    // 如果正在更新中，跳过（避免循环）
    if (isUpdatingRef.current) {
      console.log('[MarkdownTiptapEditor] 正在更新中，跳过外部value变化')
      return
    }
    
    const currentValue = value || ''
    const lastValue = lastValueRef.current
    
    // 如果 value 没有变化，跳过
    if (currentValue === lastValue) {
      console.log('[MarkdownTiptapEditor] value未变化，跳过')
      return
    }
    
    // 获取当前编辑器的 Markdown 内容
    const currentHtml = editor.getHTML()
    const currentMarkdown = htmlToMarkdown(currentHtml)
    
    // 标准化比较，避免空白字符差异
    const normalizedCurrent = currentMarkdown.trim()
    const normalizedValue = currentValue.trim()
    
    console.log('[MarkdownTiptapEditor] 外部value变化，当前编辑器内容长度:', normalizedCurrent.length, '新value长度:', normalizedValue.length)
    
    // 如果内容不同，更新编辑器
    if (normalizedCurrent !== normalizedValue) {
      console.log('[MarkdownTiptapEditor] ⚠️ 内容不同，将更新编辑器！当前内容前100字符:', normalizedCurrent.substring(0, 100))
      console.log('[MarkdownTiptapEditor] 新内容前100字符:', normalizedValue.substring(0, 100))
      isUpdatingRef.current = true
      const newHtml = markdownToHtml(currentValue)
      
      // 使用 setContent 更新内容，false 表示不触发 onUpdate
      editor.commands.setContent(newHtml, false)
      
      // 更新 ref
      lastValueRef.current = currentValue
      
      // 重置更新标志（使用 setTimeout 确保在下一个事件循环中重置）
      setTimeout(() => {
        isUpdatingRef.current = false
      }, 0)
    } else {
      // 内容相同，但 value 变化了（可能是空白字符差异），更新 ref
      console.log('[MarkdownTiptapEditor] 内容相同（仅空白字符差异），只更新ref')
      lastValueRef.current = currentValue
    }
  }, [value, editor])
  
  // 编辑器创建后，初始化 lastValueRef
  useEffect(() => {
    if (editor) {
      // 编辑器刚创建时，同步初始内容
      const initialMarkdown = value || ''
      lastValueRef.current = initialMarkdown
      
      // 确保编辑器内容与 value 一致
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

  if (!editor) {
    return <div>加载编辑器...</div>
  }

  return (
    <div style={{ position: 'relative', width: '100%', ...style }}>
      <EditorContent editor={editor} />
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

