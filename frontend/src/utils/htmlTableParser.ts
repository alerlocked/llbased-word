/**
 * VLM HTML table parser
 *
 * Splits VLM output (MinerU) by page markers, classifies rows as
 * header / data / signature, and provides structured data for the
 * HtmlTableEditor component.
 */

/** Header keywords that identify a table header row */
const HEADER_KEYWORDS = [
  '产品工号', '工序号', '工序名称', '辅助材料', '工时定额',
  '车间', '工序内容', '设备', '工艺装备', '准终', '单件',
]

/** Signature keywords that identify a signature/approval row */
const SIGNATURE_KEYWORDS = [
  '编制', '审核', '校对', '批准', '更改标记', 'M.2',
  '标记', '处数', '更改文件号', '签字', '日期',
]

export interface TablePage {
  pageNumber: number
  rawHtml: string
  editable: boolean
}

export type RowKind = 'header' | 'data' | 'signature'

/**
 * Split VLM HTML into per-page table fragments.
 *
 * VLM output format:
 *   ## 第 1 页
 *   <table>...</table>
 *   ## 第 2 页
 *   <table>...</table>
 *
 * Also handles input that is pure HTML without page markers.
 */
export function parseVlmHtml(html: string): TablePage[] {
  const pages: TablePage[] = []

  // Try splitting by "## 第 N 页" markers
  const pageRegex = /##\s*第\s*(\d+)\s*页/g
  const splits: { num: number; start: number }[] = []
  let match: RegExpExecArray | null

  while ((match = pageRegex.exec(html)) !== null) {
    splits.push({ num: parseInt(match[1], 10), start: match.index + match[0].length })
  }

  if (splits.length === 0) {
    // No page markers — treat entire input as a single page
    if (html.trim()) {
      const editable = containsEditableRows(html)
      pages.push({ pageNumber: 1, rawHtml: html.trim(), editable })
    }
    return pages
  }

  for (let i = 0; i < splits.length; i++) {
    const start = splits[i].start
    const end = i + 1 < splits.length ? splits[i + 1].start - (pageRegex.lastIndex - splits[i + 1].start) : html.length
    // Re-derive end position correctly
    const rawHtml = html.slice(
      start,
      i + 1 < splits.length ? html.indexOf('##', start) : html.length
    ).trim()

    if (rawHtml) {
      const editable = containsEditableRows(rawHtml)
      pages.push({ pageNumber: splits[i].num, rawHtml, editable })
    }
  }

  return pages.length > 0 ? pages : [{ pageNumber: 1, rawHtml: html.trim(), editable: containsEditableRows(html) }]
}

/**
 * Classify a <tr> element as header, data, or signature row.
 */
export function classifyRow(tr: HTMLTableRowElement): RowKind {
  const text = tr.textContent || ''

  // Check signature first (most specific)
  const sigCount = SIGNATURE_KEYWORDS.filter(kw => text.includes(kw)).length
  if (sigCount >= 2) return 'signature'

  // Check header
  const hdrCount = HEADER_KEYWORDS.filter(kw => text.includes(kw)).length
  if (hdrCount >= 2) return 'header'

  // Single strong header indicator in a short row
  if (hdrCount >= 1 && text.length < 80) return 'header'

  return 'data'
}

/**
 * Check if raw HTML contains at least one editable (data) row.
 */
function containsEditableRows(html: string): boolean {
  // Quick check: if there's a <table> and text that doesn't match header/sig
  const hasTable = /<table/i.test(html)
  if (!hasTable) return false
  return true // If there's a table, assume editable until rendered
}
