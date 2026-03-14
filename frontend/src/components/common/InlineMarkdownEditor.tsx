/**
 * InlineMarkdownEditor - 内联图片渲染编辑器
 * 使用 Overlay 方案在 textarea 上方覆盖透明层显示图片
 * 支持图片拖拽移动
 */
import React, { useRef, useEffect, useMemo, useState, useCallback } from 'react'

// 添加 CSS 动画（用于放置指示器闪烁）
if (typeof document !== 'undefined' && !document.head.querySelector('style[data-inline-editor]')) {
  const styleSheet = document.createElement('style')
  styleSheet.setAttribute('data-inline-editor', 'true')
  styleSheet.textContent = `
    @keyframes inline-editor-blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
  `
  document.head.appendChild(styleSheet)
}

interface ImagePosition {
  start: number
  end: number
  url: string
  alt: string
  top: number
  left: number
  height: number
}

interface InlineMarkdownEditorProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  style?: React.CSSProperties
  onFocus?: () => void
  onBlur?: () => void
  editorRef?: React.RefObject<HTMLTextAreaElement>
}

const InlineMarkdownEditor = React.forwardRef<HTMLTextAreaElement, InlineMarkdownEditorProps>(({
  value,
  onChange,
  placeholder,
  disabled = false,
  style,
  onFocus,
  onBlur,
  editorRef: externalRef
}, ref) => {
  const internalTextareaRef = useRef<HTMLTextAreaElement>(null)
  const textareaRef = externalRef || internalTextareaRef
  
  // 如果外部传入了 ref，需要同步
  React.useImperativeHandle(ref, () => textareaRef.current!, [])
  const overlayRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [imagePositions, setImagePositions] = useState<ImagePosition[]>([])
  const [draggedImage, setDraggedImage] = useState<ImagePosition | null>(null)
  const [dropIndicator, setDropIndicator] = useState<{ top: number; left: number } | null>(null)

  // 使用 Canvas 精确测量文本宽度
  const measureTextWidth = useCallback((text: string, textarea: HTMLTextAreaElement): number => {
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    if (!context) {
      // 降级方案：使用近似值
      const style = window.getComputedStyle(textarea)
      const fontSize = parseFloat(style.fontSize) || 16
      const letterSpacing = parseFloat(style.letterSpacing) || 0
      return text.length * (fontSize * 0.6 + letterSpacing)
    }
    
    const style = window.getComputedStyle(textarea)
    const font = `${style.fontSize} ${style.fontFamily}`
    context.font = font
    return context.measureText(text).width
  }, [])

  // 精确计算文本在 textarea 中的位置
  const getTextPosition = useCallback((textarea: HTMLTextAreaElement, charIndex: number): { top: number; left: number } => {
    if (charIndex < 0) charIndex = 0
    if (charIndex > textarea.value.length) charIndex = textarea.value.length
    
    const text = textarea.value.substring(0, charIndex)
    const lines = text.split('\n')
    const lineNumber = lines.length - 1
    const currentLineText = lines[lineNumber] || ''
    
    // 获取样式
    const computedStyle = window.getComputedStyle(textarea)
    const lineHeight = parseFloat(computedStyle.lineHeight) || 20.4286
    const paddingTop = parseFloat(computedStyle.paddingTop) || 4
    const paddingLeft = parseFloat(computedStyle.paddingLeft) || 11
    
    // 计算当前行的文本宽度（精确测量）
    const lineWidth = measureTextWidth(currentLineText, textarea)
    
    // 计算位置（考虑滚动偏移）
    const top = lineNumber * lineHeight + paddingTop
    const left = lineWidth + paddingLeft
    
    return { top, left }
  }, [measureTextWidth])

  // 解析 Markdown 中的图片并计算位置（使用 useMemo 缓存）
  const imagePositionsMemo = useMemo(() => {
    const textarea = textareaRef.current
    // 边界情况处理：空内容、没有 textarea
    if (!textarea || !value || !value.trim()) {
      return []
    }

    // 快速检查：如果没有图片语法，直接返回空数组
    if (!value.includes('![') || !value.includes('](')) {
      return []
    }

    // 预处理：合并跨行的图片语法
    const processedContent = value.replace(/!\[([^\]]*)\]\s*[\r\n]+\s*\(([^)]+)\)/g, '![$1]($2)')

    // 解析所有图片
    const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g
    const images: ImagePosition[] = []
    let match

    while ((match = imageRegex.exec(processedContent)) !== null) {
      const [fullMatch, alt, url] = match
      const start = match.index
      const end = start + fullMatch.length

      // 使用精确的位置计算
      const position = getTextPosition(textarea, start)

      // 处理图片 URL
      let imageUrl = url.trim().replace(/^["']|["']$/g, '')
      if (!imageUrl) {
        continue // 跳过无效 URL
      }
      
      if (!imageUrl.startsWith('http://') && !imageUrl.startsWith('https://')) {
        if (!imageUrl.startsWith('/')) {
          imageUrl = '/' + imageUrl
        }
        imageUrl = `http://localhost:8000${imageUrl}`
      }

      images.push({
        start,
        end,
        url: imageUrl,
        alt: alt || '图片',
        top: position.top,
        left: position.left,
        height: 200 // 默认高度，图片加载后会调整
      })
    }

    return images
  }, [value, getTextPosition])

  // 更新图片位置状态
  useEffect(() => {
    setImagePositions(imagePositionsMemo)
  }, [imagePositionsMemo])

  // 处理窗口大小变化，重新计算位置
  useEffect(() => {
    const handleResize = () => {
      // 触发重新计算（通过依赖 value 的 useMemo）
      setImagePositions(prev => [...prev]) // 触发重新渲染
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])


  // 同步滚动
  useEffect(() => {
    const textarea = textareaRef.current
    const overlay = overlayRef.current
    if (!textarea || !overlay) return

    const syncScroll = () => {
      overlay.scrollTop = textarea.scrollTop
      overlay.scrollLeft = textarea.scrollLeft
    }

    textarea.addEventListener('scroll', syncScroll)
    return () => textarea.removeEventListener('scroll', syncScroll)
  }, [])

  // 处理图片加载完成，更新高度
  const handleImageLoad = useCallback((img: HTMLImageElement, positionKey: string) => {
    setImagePositions(prev => {
      return prev.map(pos => {
        if (`${pos.start}-${pos.end}` === positionKey) {
          return {
            ...pos,
            height: Math.min(img.naturalHeight, 300) // 限制最大高度
          }
        }
        return pos
      })
    })
  }, [])

  // 计算拖拽放置位置（根据鼠标坐标计算字符索引）
  const getDropPosition = useCallback((textarea: HTMLTextAreaElement, e: React.DragEvent): number => {
    const rect = textarea.getBoundingClientRect()
    const x = e.clientX - rect.left + textarea.scrollLeft
    const y = e.clientY - rect.top + textarea.scrollTop
    
    // 获取样式
    const style = window.getComputedStyle(textarea)
    const lineHeight = parseFloat(style.lineHeight) || 20.4286
    const paddingTop = parseFloat(style.paddingTop) || 4
    
    // 计算行号
    const adjustedY = y - paddingTop
    const line = Math.max(0, Math.floor(adjustedY / lineHeight))
    
    // 获取该行的文本
    const lines = textarea.value.split('\n')
    if (line >= lines.length) {
      return textarea.value.length
    }
    
    // 计算该行的字符位置
    const lineText = lines[line]
    const paddingLeft = parseFloat(style.paddingLeft) || 11
    const adjustedX = x - paddingLeft
    
    // 使用二分查找找到最接近的字符位置
    let charIndex = 0
    let minDiff = Infinity
    for (let i = 0; i <= lineText.length; i++) {
      const textBefore = lineText.substring(0, i)
      const width = measureTextWidth(textBefore, textarea)
      const diff = Math.abs(width - adjustedX)
      if (diff < minDiff) {
        minDiff = diff
        charIndex = i
      }
    }
    
    // 计算总字符索引
    let totalIndex = 0
    for (let i = 0; i < line && i < lines.length; i++) {
      totalIndex += lines[i].length + 1 // +1 for newline
    }
    totalIndex += charIndex
    
    return Math.min(totalIndex, textarea.value.length)
  }, [measureTextWidth])

  // 处理拖拽开始
  const handleDragStart = useCallback((e: React.DragEvent, img: ImagePosition) => {
    setDraggedImage(img)
    // 获取原始 URL（去掉 http://localhost:8000 前缀）
    let originalUrl = img.url
    if (originalUrl.startsWith('http://localhost:8000')) {
      originalUrl = originalUrl.replace('http://localhost:8000', '')
    }
    e.dataTransfer.setData('text/plain', JSON.stringify({
      type: 'image',
      markdown: `![${img.alt}](${originalUrl})`,
      start: img.start,
      end: img.end
    }))
    e.dataTransfer.effectAllowed = 'move'
    // 设置拖拽图片为半透明
    if (e.currentTarget instanceof HTMLElement) {
      e.currentTarget.style.opacity = '0.5'
    }
  }, [])

  // 处理拖拽结束
  const handleDragEnd = useCallback((e: React.DragEvent) => {
    setDraggedImage(null)
    setDropIndicator(null)
    // 恢复透明度
    if (e.currentTarget instanceof HTMLElement) {
      e.currentTarget.style.opacity = '1'
    }
  }, [])

  // 处理拖拽悬停
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    
    const textarea = textareaRef.current
    if (!textarea) return
    
    // 计算并显示放置位置指示器
    const position = getDropPosition(textarea, e)
    const pos = getTextPosition(textarea, position)
    setDropIndicator(pos)
  }, [getDropPosition, getTextPosition])

  // 处理拖拽放置
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDropIndicator(null)
    
    try {
      const dataStr = e.dataTransfer.getData('text/plain')
      if (!dataStr) return
      
      const data = JSON.parse(dataStr)
      if (data.type !== 'image') return
      
      const textarea = textareaRef.current
      if (!textarea) return
      
      // 计算放置位置
      const dropPosition = getDropPosition(textarea, e)
      
      // 删除原位置并插入新位置
      let newContent = value
      const markdownLength = data.end - data.start
      
      if (dropPosition <= data.start) {
        // 放置位置在原位置之前
        // 先删除原位置
        newContent = newContent.slice(0, data.start) + newContent.slice(data.end)
        // 再在新位置插入
        newContent = newContent.slice(0, dropPosition) + data.markdown + newContent.slice(dropPosition)
      } else if (dropPosition >= data.end) {
        // 放置位置在原位置之后
        // 先删除原位置
        newContent = newContent.slice(0, data.start) + newContent.slice(data.end)
        // 调整放置位置（因为删除了原内容）
        const adjustedPosition = dropPosition - markdownLength
        // 再在新位置插入
        newContent = newContent.slice(0, adjustedPosition) + data.markdown + newContent.slice(adjustedPosition)
      } else {
        // 放置位置在原位置内部，不移动
        return
      }
      
      onChange(newContent)
      
      // 更新光标位置
      setTimeout(() => {
        if (textarea) {
          const newCursorPos = dropPosition < data.start 
            ? dropPosition + data.markdown.length 
            : dropPosition - markdownLength + data.markdown.length
          textarea.setSelectionRange(newCursorPos, newCursorPos)
          textarea.focus()
        }
      }, 0)
    } catch (error) {
      console.error('拖拽处理失败:', error)
    }
  }, [value, onChange, getDropPosition])

  // 基础样式（与 textarea 保持一致）
  const baseStyle: React.CSSProperties = {
    fontSize: 16,
    lineHeight: 1.9,
    fontFamily: '"Noto Serif SC", "Source Han Serif CN", Georgia, serif',
    letterSpacing: '0.02em',
    padding: '4px 11px',
    ...style
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {/* 底层：textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        onFocus={onFocus}
        onBlur={onBlur}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onDragLeave={() => setDropIndicator(null)}
        style={{
          ...baseStyle,
          width: '100%',
          minHeight: 'calc(100vh - 160px)',
          border: 'none',
          outline: 'none',
          resize: 'none',
          background: 'transparent',
          color: 'inherit',
          zIndex: 1,
          position: 'relative'
        }}
      />

      {/* 顶层：图片渲染层 */}
      <div
        ref={overlayRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'none', // 不阻挡 textarea 的交互
          zIndex: 2,
          overflow: 'hidden',
          ...baseStyle,
          padding: baseStyle.padding
        }}
      >
        {imagePositions.map((img, index) => {
          const positionKey = `${img.start}-${img.end}`
          const isDragging = draggedImage?.start === img.start && draggedImage?.end === img.end
          return (
            <div
              key={positionKey}
              draggable={true}
              onDragStart={(e) => handleDragStart(e, img)}
              onDragEnd={handleDragEnd}
              style={{
                position: 'absolute',
                top: `${img.top}px`,
                left: `${img.left}px`,
                pointerEvents: 'auto', // 图片可以交互（如右键菜单）
                maxWidth: '400px',
                zIndex: 3,
                cursor: 'move',
                opacity: isDragging ? 0.5 : 1,
                transition: isDragging ? 'none' : 'opacity 0.2s'
              }}
            >
              <img
                src={img.url}
                alt={img.alt}
                draggable={false} // 防止图片本身被拖拽
                style={{
                  maxWidth: '100%',
                  maxHeight: `${img.height}px`,
                  height: 'auto',
                  borderRadius: 4,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                  display: 'block',
                  background: '#f5f5f5',
                  userSelect: 'none' // 防止选中
                }}
                loading="lazy"
                onLoad={(e) => handleImageLoad(e.currentTarget, positionKey)}
                onError={(e) => {
                  // 图片加载失败时隐藏
                  e.currentTarget.style.display = 'none'
                }}
              />
            </div>
          )
        })}
        
        {/* 拖拽放置位置指示器 */}
        {dropIndicator && (
          <div
            style={{
              position: 'absolute',
              top: `${dropIndicator.top}px`,
              left: `${dropIndicator.left}px`,
              width: '2px',
              height: '20px',
              background: '#1890ff',
              zIndex: 4,
              pointerEvents: 'none',
              animation: 'inline-editor-blink 1s infinite'
            }}
          />
        )}
      </div>
    </div>
  )
})

InlineMarkdownEditor.displayName = 'InlineMarkdownEditor'

export default InlineMarkdownEditor

