/**
 * Markdown ↔ HTML 双向转换工具
 * 用于 Tiptap 编辑器和 Markdown 存储格式之间的转换
 */
import TurndownService from 'turndown'
import MarkdownIt from 'markdown-it'

// 初始化 Markdown 解析器
const md = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true
})

// 初始化 HTML 转 Markdown 转换器
const turndownService = new TurndownService({
  headingStyle: 'atx',
  codeBlockStyle: 'fenced',
  bulletListMarker: '-'
})

// 自定义图片规则：将 <img> 转换为 Markdown 图片语法
turndownService.addRule('image', {
  filter: 'img',
  replacement: (_content, node) => {
    const img = node as HTMLImageElement
    const alt = img.alt || img.getAttribute('alt') || ''
    let src = img.src || img.getAttribute('src') || ''
    
    // 移除后端地址前缀，使用相对路径
    if (src.startsWith('http://localhost:8000')) {
      src = src.replace('http://localhost:8000', '')
    }
    // 处理错误的端口号（浏览器可能将相对路径解析为 localhost:3000）
    if (src.startsWith('http://localhost:3000')) {
      src = src.replace('http://localhost:3000', '')
    }
    
    // 确保路径以 / 开头
    if (src && !src.startsWith('/') && !src.startsWith('http://') && !src.startsWith('https://') && !src.startsWith('data:')) {
      src = '/' + src
    }
    
    // 清理 alt 文本中的特殊字符（避免 Markdown 语法错误）
    const cleanAlt = alt.replace(/[\[\]()]/g, '').trim() || '图片'
    
    return `![${cleanAlt}](${src})`
  }
})

/**
 * 将 Markdown 转换为 HTML
 */
export function markdownToHtml(markdown: string): string {
  if (!markdown || !markdown.trim()) {
    return '<p></p>'
  }
  
  // 预处理：合并跨行的图片语法
  const processedMarkdown = markdown.replace(
    /!\[([^\]]*)\]\s*[\r\n]+\s*\(([^)]+)\)/g,
    '![$1]($2)'
  )
  
  // 使用 markdown-it 解析
  let html = md.render(processedMarkdown)
  
  // 处理图片 URL：如果是相对路径，添加后端地址
  html = html.replace(
    /<img([^>]*?)src="([^"]+)"([^>]*?)>/g,
    (match, before, src, after) => {
      // 调试日志
      console.log('[markdownToHtml] 处理图片URL:', src)
      
      // 如果已经是完整 URL（包括 data URL），需要检查是否是错误的端口
      if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('data:')) {
        // 如果URL包含 localhost:3000，说明是错误的前端地址，需要替换为后端地址
        if (src.includes('localhost:3000')) {
          let correctedSrc = src.replace('localhost:3000', 'localhost:8000')
          // 处理URL中的空格，替换为下划线（因为文件系统路径中可能有空格）
          correctedSrc = correctedSrc.replace(/ /g, '_')
          console.log('[markdownToHtml] 修正端口:3000->8000，处理空格:', correctedSrc)
          return `<img${before}src="${correctedSrc}"${after} onerror="this.onerror=null; this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'200\' height=\'200\'%3E%3Ctext x=\'50%25\' y=\'50%25\' text-anchor=\'middle\' dy=\'.3em\' fill=\'%23999\'%3E图片加载失败%3C/text%3E%3C/svg%3E';" loading="lazy">`
        }
        console.log('[markdownToHtml] 完整URL，直接返回')
        return match
      }
      
      // 相对路径，添加后端地址
      // 确保路径格式正确
      let normalizedSrc = src.trim()
      
      // 移除可能的引号
      normalizedSrc = normalizedSrc.replace(/^["']|["']$/g, '')
      
      // 如果路径为空，返回原匹配
      if (!normalizedSrc) {
        console.log('[markdownToHtml] 路径为空，返回原匹配')
        return match
      }
      
      // 如果已经包含 localhost:8000，说明已经处理过，直接返回
      if (normalizedSrc.includes('localhost:8000')) {
        console.log('[markdownToHtml] 已包含localhost:8000，直接返回')
        return match
      }
      
      // 确保路径以 / 开头
      if (!normalizedSrc.startsWith('/')) {
        normalizedSrc = '/' + normalizedSrc
      }
      
      // 移除重复的斜杠
      normalizedSrc = normalizedSrc.replace(/\/+/g, '/')
      
      const fullUrl = `http://localhost:8000${normalizedSrc}`
      console.log('[markdownToHtml] 转换后的URL:', fullUrl)
      
      // 添加错误处理属性
      return `<img${before}src="${fullUrl}"${after} onerror="this.onerror=null; this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'200\' height=\'200\'%3E%3Ctext x=\'50%25\' y=\'50%25\' text-anchor=\'middle\' dy=\'.3em\' fill=\'%23999\'%3E图片加载失败%3C/text%3E%3C/svg%3E';" loading="lazy">`
    }
  )
  
  return html
}

/**
 * 将 HTML 转换为 Markdown
 */
export function htmlToMarkdown(html: string): string {
  if (!html || !html.trim()) {
    return ''
  }
  
  // 处理图片 URL：移除后端地址前缀，保留相对路径
  const processedHtml = html.replace(
    /<img([^>]*?)src="http:\/\/localhost:8000([^"]+)"([^>]*?)>/g,
    (_match, before, path, after) => {
      // 确保路径以 / 开头
      const normalizedPath = path.startsWith('/') ? path : '/' + path
      return `<img${before}src="${normalizedPath}"${after}>`
    }
  ).replace(
    /<img([^>]*?)src="http:\/\/localhost:3000([^"]+)"([^>]*?)>/g,
    (_match, before, path, after) => {
      // 修正错误的端口号并移除前缀
      const normalizedPath = path.startsWith('/') ? path : '/' + path
      return `<img${before}src="${normalizedPath}"${after}>`
    }
  )
  
  // 使用 turndown 转换
  let markdown = turndownService.turndown(processedHtml)
  
  // 清理多余的换行
  markdown = markdown.replace(/\n{3,}/g, '\n\n')
  
  return markdown.trim()
}

