/**
 * Markdown ↔ HTML 双向转换工具
 * 用于 Tiptap 编辑器和 Markdown 存储格式之间的转换
 */
import TurndownService from 'turndown'
import MarkdownIt from 'markdown-it'

// 后端基础路径（通过 Vite proxy 或同源访问）
const API_BASE = import.meta.env.VITE_API_BASE || ''

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

/**
 * 将相对路径的图片 src 转为完整后端 URL
 */
function resolveImageUrl(src: string): string {
  if (!src) return src
  // 已经是完整 URL 或 data URL，直接返回
  if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('data:')) return src
  // 相对路径，加上 API_BASE 前缀
  const normalized = src.startsWith('/') ? src : '/' + src
  return `${API_BASE}${normalized}`
}

/**
 * 将完整后端 URL 的图片 src 转回相对路径
 */
function stripImageUrl(src: string): string {
  if (!src) return src
  if (API_BASE && src.startsWith(API_BASE)) {
    return src.slice(API_BASE.length) || '/'
  }
  // 兼容旧数据中硬编码的 localhost:8000
  return src.replace(/^https?:\/\/localhost:\d+/, '')
}

// 自定义图片规则：将 <img> 转换为 Markdown 图片语法
turndownService.addRule('image', {
  filter: 'img',
  replacement: (_content, node) => {
    const img = node as HTMLImageElement
    const alt = img.alt || img.getAttribute('alt') || ''
    let src = img.src || img.getAttribute('src') || ''
    
    // 转回相对路径
    src = stripImageUrl(src)
    
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
  
  // 处理图片 URL：相对路径转完整 URL
  html = html.replace(
    /<img([^>]*?)src="([^"]+)"([^>]*?)>/g,
    (match, before, src, after) => {
      // data URL 直接返回
      if (src.startsWith('data:')) return match
      
      // 已经是完整 http(s) URL，保留原样
      if (src.startsWith('http://') || src.startsWith('https://')) return match
      
      // 相对路径，转为完整后端 URL
      const fullUrl = resolveImageUrl(src)
      
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
    /<img([^>]*?)src="([^"]+)"([^>]*?)>/g,
    (match, before, src, after) => {
      const stripped = stripImageUrl(src)
      const normalized = stripped.startsWith('/') ? stripped : '/' + stripped
      return `<img${before}src="${normalized}"${after}>`
    }
  )
  
  // 使用 turndown 转换
  let markdown = turndownService.turndown(processedHtml)
  
  // 清理多余的换行
  markdown = markdown.replace(/\n{3,}/g, '\n\n')
  
  return markdown.trim()
}
