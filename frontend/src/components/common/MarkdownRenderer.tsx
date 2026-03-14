/**
 * MarkdownRenderer - 简单的 Markdown 渲染组件
 * 支持图片、链接、标题等基本语法
 */
import React from 'react'

interface MarkdownRendererProps {
  content: string
  className?: string
  style?: React.CSSProperties
}

/**
 * 简单的 Markdown 渲染器
 * 将 Markdown 语法转换为 HTML 元素
 */
const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ 
  content, 
  className,
  style 
}) => {
  // 解析 Markdown 内容
  const renderContent = () => {
    if (!content) return null

    // 预处理：合并跨行的图片语法
    // 将 ![alt]\n(url) 格式合并为 ![alt](url)
    // 支持多种空格和换行组合，包括 Windows 和 Unix 换行符
    let processedContent = content.replace(/!\[([^\]]*)\]\s*[\r\n]+\s*\(([^)]+)\)/g, '![$1]($2)')

    // 按行分割
    const lines = processedContent.split('\n')
    const elements: React.ReactNode[] = []
    let currentParagraph: string[] = []
    let skipNext = false

    const flushParagraph = () => {
      if (currentParagraph.length > 0) {
        const paragraphText = currentParagraph.join('\n')
        elements.push(
          <p key={`p-${elements.length}`} style={{ marginBottom: '1em', lineHeight: 1.8 }}>
            {renderInline(paragraphText)}
          </p>
        )
        currentParagraph = []
      }
    }

    for (let index = 0; index < lines.length; index++) {
      const line = lines[index]
      
      // 如果上一行标记跳过，则跳过当前行
      if (skipNext) {
        skipNext = false
        continue
      }
      // 标题
      if (line.match(/^#{1,6}\s+/)) {
        flushParagraph()
        const level = line.match(/^(#{1,6})/)?.[1].length || 1
        const text = line.replace(/^#{1,6}\s+/, '')
        const Tag = `h${Math.min(level, 6)}` as keyof JSX.IntrinsicElements
        elements.push(
          <Tag key={`h-${index}`} style={{ 
            marginTop: '1.5em', 
            marginBottom: '0.5em',
            fontWeight: 'bold'
          }}>
            {renderInline(text)}
          </Tag>
        )
        continue
      }

      // 空行
      if (line.trim() === '') {
        flushParagraph()
        continue
      }

      // 图片语法：![alt](url) - 支持完整格式和拆分格式
      // 完整格式：![alt](url) - 可以在行中任何位置
      // 拆分格式：![alt]\n(url) - 跨行格式
      const imageMatchFull = line.match(/!\[(.*?)\]\(([^)]+)\)/)
      if (imageMatchFull) {
        // 检查是否是独立行的图片（前后没有其他文本）
        const imagePart = imageMatchFull[0]
        const beforeImage = line.substring(0, line.indexOf(imagePart)).trim()
        const afterImage = line.substring(line.indexOf(imagePart) + imagePart.length).trim()
        const isStandaloneImage = !beforeImage && !afterImage
        
        if (isStandaloneImage) {
          // 独立行的图片，作为块级元素
          flushParagraph()
          const [, alt, url] = imageMatchFull
          // 处理URL：如果是相对路径，添加后端地址
          let imageUrl = url.trim()
          // 移除可能的引号
          imageUrl = imageUrl.replace(/^["']|["']$/g, '')
          if (imageUrl && !imageUrl.startsWith('http://') && !imageUrl.startsWith('https://')) {
            // 确保路径以 / 开头
            if (!imageUrl.startsWith('/')) {
              imageUrl = '/' + imageUrl
            }
            imageUrl = `http://localhost:8000${imageUrl}`
          }
          if (imageUrl) {
            elements.push(
              <div key={`img-${index}`} style={{ 
                margin: '1.5em 0', 
                textAlign: 'center',
                padding: '8px',
                background: '#fafafa',
                borderRadius: 8,
                border: '1px solid #e8e8e8'
              }}>
                <img 
                  src={imageUrl} 
                  alt={alt || '图片'} 
                  style={{ 
                    maxWidth: '100%', 
                    height: 'auto',
                    borderRadius: 4,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    display: 'block',
                    margin: '0 auto'
                  }}
                  loading="lazy"
                  onError={(e) => {
                    // 加载失败时显示占位符
                    const target = e.target as HTMLImageElement
                    const parent = target.parentElement
                    if (parent && !parent.querySelector('.image-error')) {
                      target.style.display = 'none'
                      const errorDiv = document.createElement('div')
                      errorDiv.className = 'image-error'
                      errorDiv.style.cssText = 'padding: 40px 20px; text-align: center; color: #999; border: 2px dashed #ddd; border-radius: 8px; background: #f5f5f5;'
                      errorDiv.innerHTML = `
                        <div style="font-size: 48px; margin-bottom: 8px;">🖼️</div>
                        <div style="font-size: 14px; color: #999;">图片加载失败</div>
                        <div style="font-size: 12px; color: #bbb; margin-top: 4px;">${alt || url.substring(0, 30)}...</div>
                      `
                      parent.appendChild(errorDiv)
                    }
                  }}
                  onLoad={(e) => {
                    // 图片加载成功，移除可能的错误提示
                    const target = e.target as HTMLImageElement
                    const parent = target.parentElement
                    if (parent) {
                      const errorDiv = parent.querySelector('.image-error')
                      if (errorDiv) {
                        errorDiv.remove()
                      }
                    }
                  }}
                />
                {alt && alt.trim() && (
                  <div style={{ 
                    marginTop: '12px', 
                    fontSize: '13px', 
                    color: '#666',
                    fontStyle: 'italic',
                    lineHeight: 1.5
                  }}>
                    {alt}
                  </div>
                )}
              </div>
            )
          }
          continue
        } else {
          // 行内图片，作为段落的一部分处理
          // 不在这里处理，让 renderInline 处理
        }
      }
      
      // 处理拆分格式：![alt] 在上一行，下一行是 (url)
      // 支持行尾有其他内容的情况，如：![alt]文本 或 (url)文本
      const imageAltMatch = line.match(/!\[(.*?)\]/)
      if (imageAltMatch && index < lines.length - 1) {
        // 检查当前行是否只有图片alt（可能后面有文本）
        const altPart = imageAltMatch[0]
        const afterAlt = line.substring(line.indexOf(altPart) + altPart.length).trim()
        
        // 检查下一行是否包含URL
        const nextLine = lines[index + 1]
        const urlMatch = nextLine.match(/\(([^)]+)\)/)
        if (urlMatch) {
          flushParagraph()
          const [, alt] = imageAltMatch
          const [, url] = urlMatch
          let imageUrl = url.trim()
          // 移除可能的引号
          imageUrl = imageUrl.replace(/^["']|["']$/g, '')
          if (imageUrl && !imageUrl.startsWith('http://') && !imageUrl.startsWith('https://')) {
            // 确保路径以 / 开头
            if (!imageUrl.startsWith('/')) {
              imageUrl = '/' + imageUrl
            }
            imageUrl = `http://localhost:8000${imageUrl}`
          }
          if (imageUrl) {
            elements.push(
              <div key={`img-${index}`} style={{ 
                margin: '1.5em 0', 
                textAlign: 'center',
                padding: '8px',
                background: '#fafafa',
                borderRadius: 8,
                border: '1px solid #e8e8e8'
              }}>
                <img 
                  src={imageUrl} 
                  alt={alt || '图片'} 
                  style={{ 
                    maxWidth: '100%', 
                    height: 'auto',
                    borderRadius: 4,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                    display: 'block',
                    margin: '0 auto'
                  }}
                  loading="lazy"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    const parent = target.parentElement
                    if (parent && !parent.querySelector('.image-error')) {
                      target.style.display = 'none'
                      const errorDiv = document.createElement('div')
                      errorDiv.className = 'image-error'
                      errorDiv.style.cssText = 'padding: 40px 20px; text-align: center; color: #999; border: 2px dashed #ddd; border-radius: 8px; background: #f5f5f5;'
                      errorDiv.innerHTML = `
                        <div style="font-size: 48px; margin-bottom: 8px;">🖼️</div>
                        <div style="font-size: 14px; color: #999;">图片加载失败</div>
                        <div style="font-size: 12px; color: #bbb; margin-top: 4px;">${alt || url.substring(0, 30)}...</div>
                      `
                      parent.appendChild(errorDiv)
                    }
                  }}
                  onLoad={(e) => {
                    const target = e.target as HTMLImageElement
                    const parent = target.parentElement
                    if (parent) {
                      const errorDiv = parent.querySelector('.image-error')
                      if (errorDiv) {
                        errorDiv.remove()
                      }
                    }
                  }}
                />
                {alt && alt.trim() && (
                  <div style={{ 
                    marginTop: '12px', 
                    fontSize: '13px', 
                    color: '#666',
                    fontStyle: 'italic',
                    lineHeight: 1.5
                  }}>
                    {alt}
                  </div>
                )}
              </div>
            )
          }
          
          // 处理当前行图片alt后的文本
          if (afterAlt) {
            currentParagraph.push(afterAlt)
          }
          
          // 处理下一行URL后的文本
          const urlPart = urlMatch[0]
          const afterUrl = nextLine.substring(nextLine.indexOf(urlPart) + urlPart.length).trim()
          if (afterUrl) {
            currentParagraph.push(afterUrl)
          }
          
          // 标记跳过下一行（URL行）
          skipNext = true
          continue
        }
      }
      
      // 如果是URL行（上一行是图片alt），跳过
      if (index > 0) {
        const prevLine = lines[index - 1]
        const urlMatch = line.match(/^\(([^)]+)\)/)
        if (urlMatch && prevLine && prevLine.match(/!\[.*?\]/)) {
          continue // 已经在上一行处理过了
        }
      }

      // 普通文本行
      currentParagraph.push(line)
    }

    flushParagraph()

    return elements.length > 0 ? elements : <p>{content}</p>
  }

  // 渲染行内元素（链接、粗体、斜体等）
  const renderInline = (text: string): React.ReactNode => {
    if (!text) return null

    // 图片语法（行内）
    const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g
    const parts: React.ReactNode[] = []
    let lastIndex = 0
    let match
    let keyIndex = 0

    while ((match = imageRegex.exec(text)) !== null) {
      // 添加图片前的文本
      if (match.index > lastIndex) {
        parts.push(renderTextWithFormatting(text.substring(lastIndex, match.index), keyIndex++))
      }

      // 添加图片
      const [, alt, url] = match
      let imageUrl = url.trim()
      // 移除可能的引号
      imageUrl = imageUrl.replace(/^["']|["']$/g, '')
      if (imageUrl && !imageUrl.startsWith('http://') && !imageUrl.startsWith('https://')) {
        // 确保路径以 / 开头
        if (!imageUrl.startsWith('/')) {
          imageUrl = '/' + imageUrl
        }
        imageUrl = `http://localhost:8000${imageUrl}`
      }
      parts.push(
        <img 
          key={`inline-img-${keyIndex++}`}
          src={imageUrl} 
          alt={alt || '图片'} 
          style={{ 
            maxWidth: '100%', 
            height: 'auto',
            verticalAlign: 'middle',
            margin: '0 4px',
            maxHeight: '200px',
            borderRadius: 4,
            boxShadow: '0 1px 4px rgba(0,0,0,0.1)'
          }}
          loading="lazy"
          onError={(e) => {
            const target = e.target as HTMLImageElement
            target.style.display = 'none'
          }}
        />
      )

      lastIndex = match.index + match[0].length
    }

    // 添加剩余文本
    if (lastIndex < text.length) {
      parts.push(renderTextWithFormatting(text.substring(lastIndex), keyIndex++))
    }

    return parts.length > 0 ? parts : text
  }

  // 渲染文本格式（粗体、斜体、链接）
  const renderTextWithFormatting = (text: string, keyBase: number): React.ReactNode => {
    const parts: React.ReactNode[] = []
    let lastIndex = 0
    let keyIndex = 0

    // 链接：[text](url)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g
    let match

    while ((match = linkRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        const beforeText = text.substring(lastIndex, match.index)
        parts.push(renderBoldItalic(beforeText, keyBase + keyIndex++))
      }

      const [, linkText, linkUrl] = match
      parts.push(
        <a 
          key={`link-${keyBase}-${keyIndex++}`}
          href={linkUrl} 
          target="_blank" 
          rel="noopener noreferrer"
          style={{ color: '#1890ff', textDecoration: 'none' }}
        >
          {linkText}
        </a>
      )

      lastIndex = match.index + match[0].length
    }

    if (lastIndex < text.length) {
      const remaining = text.substring(lastIndex)
      parts.push(renderBoldItalic(remaining, keyBase + keyIndex++))
    }

    return parts.length > 0 ? parts : text
  }

  // 渲染粗体和斜体
  const renderBoldItalic = (text: string, keyBase: number): React.ReactNode => {
    const parts: React.ReactNode[] = []
    let processed = text
    let keyIndex = 0

    // 粗体：**text** 或 __text__
    processed = processed.replace(/\*\*(.*?)\*\*/g, (_, content) => {
      const key = `bold-${keyBase}-${keyIndex++}`
      parts.push(<strong key={key}>{content}</strong>)
      return `__BOLD_${keyIndex - 1}__`
    })

    processed = processed.replace(/__(.*?)__/g, (_, content) => {
      const key = `bold-${keyBase}-${keyIndex++}`
      parts.push(<strong key={key}>{content}</strong>)
      return `__BOLD_${keyIndex - 1}__`
    })

    // 斜体：*text* 或 _text_
    processed = processed.replace(/\*(.*?)\*/g, (_, content) => {
      if (content.includes('__BOLD_')) {
        return `*${content}*`
      }
      const key = `italic-${keyBase}-${keyIndex++}`
      parts.push(<em key={key}>{content}</em>)
      return `__ITALIC_${keyIndex - 1}__`
    })

    processed = processed.replace(/_(.*?)_/g, (_, content) => {
      if (content.includes('__BOLD_') || content.includes('__ITALIC_')) {
        return `_${content}_`
      }
      const key = `italic-${keyBase}-${keyIndex++}`
      parts.push(<em key={key}>{content}</em>)
      return `__ITALIC_${keyIndex - 1}__`
    })

    // 恢复占位符
    processed = processed.replace(/__BOLD_(\d+)__/g, (_, idx) => {
      return parts[parseInt(idx)] as any
    })

    processed = processed.replace(/__ITALIC_(\d+)__/g, (_, idx) => {
      return parts[parseInt(idx)] as any
    })

    return parts.length > 0 ? (
      <>
        {processed.split(/(__BOLD_\d+__|__ITALIC_\d+__)/).map((part, idx) => {
          if (part.match(/__BOLD_(\d+)__/)) {
            const match = part.match(/__BOLD_(\d+)__/)
            return parts[parseInt(match![1])]
          }
          if (part.match(/__ITALIC_(\d+)__/)) {
            const match = part.match(/__ITALIC_(\d+)__/)
            return parts[parseInt(match![1])]
          }
          return part ? <span key={`text-${keyBase}-${idx}`}>{part}</span> : null
        })}
      </>
    ) : text
  }

  return (
    <div 
      className={className}
      style={{
        fontFamily: '"Noto Serif SC", "Source Han Serif CN", Georgia, serif',
        fontSize: 16,
        lineHeight: 1.9,
        color: '#333',
        ...style
      }}
    >
      {renderContent()}
    </div>
  )
}

export default MarkdownRenderer

