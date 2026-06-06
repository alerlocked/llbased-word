/**
 * HTML Cell Patcher
 *
 * Merges AI-generated HTML table rows into the existing VLM HTML table.
 * Strategy: match by row+column position, only update textContent of
 * data cells. Preserves colspan, rowspan, and DOM structure.
 */

/**
 * Patch table cells in the original HTML with content from generated HTML.
 *
 * Both inputs are full HTML strings containing <table> elements.
 * Generated HTML may contain fewer pages/rows — we match by sequential
 * position across all tables.
 *
 * Only data cells (not header/signature rows) are updated.
 */
export function patchTableCells(original: string, generated: string): string {
  const parser = new DOMParser()

  const originalDoc = parser.parseFromString(original, 'text/html')
  const generatedDoc = parser.parseFromString(generated, 'text/html')

  const originalTables = originalDoc.querySelectorAll('table')
  const generatedTables = generatedDoc.querySelectorAll('table')

  // Flatten all data rows across all tables, keeping a global index
  const origDataRows = collectDataRows(originalTables)
  const genDataRows = collectDataRows(generatedTables)

  // Match by position and update textContent
  for (let i = 0; i < Math.min(origDataRows.length, genDataRows.length); i++) {
    const origCells = origDataRows[i].querySelectorAll('td')
    const genCells = genDataRows[i].querySelectorAll('td')

    for (let j = 0; j < Math.min(origCells.length, genCells.length); j++) {
      origCells[j].textContent = genCells[j].textContent?.trim() || ''
    }
  }

  // Reconstruct HTML from modified original document
  // Collect all table outerHTML
  const tables = originalDoc.querySelectorAll('table')
  const parts: string[] = []
  tables.forEach((table, idx) => {
    // Check if there were page markers in the original
    parts.push(table.outerHTML)
  })

  return parts.join('\n')
}

/**
 * Collect data rows from all tables (skipping header and signature rows).
 * Uses the same classification logic as htmlTableParser.
 */
function collectDataRows(tables: NodeListOf<HTMLTableElement>): HTMLTableRowElement[] {
  const HEADER_KEYWORDS = [
    '产品工号', '工序号', '工序名称', '辅助材料', '工时定额',
    '车间', '工序内容', '设备', '工艺装备', '准终', '单件',
  ]
  const SIGNATURE_KEYWORDS = [
    '编制', '审核', '校对', '批准', '更改标记', 'M.2',
    '标记', '处数', '更改文件号', '签字', '日期',
  ]

  const dataRows: HTMLTableRowElement[] = []

  tables.forEach(table => {
    const rows = table.querySelectorAll('tr')
    rows.forEach(tr => {
      const text = tr.textContent || ''
      const sigCount = SIGNATURE_KEYWORDS.filter(kw => text.includes(kw)).length
      if (sigCount >= 2) return // signature row — skip

      const hdrCount = HEADER_KEYWORDS.filter(kw => text.includes(kw)).length
      if (hdrCount >= 2) return // header row — skip
      if (hdrCount >= 1 && text.length < 80) return // short header — skip

      dataRows.push(tr)
    })
  })

  return dataRows
}
