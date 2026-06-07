/**
 * ProcessTableEditor — Renders chapter data as proper process document tables.
 *
 * Uses layout definitions from processDocumentLayouts.ts to render tables
 * with grouped headers (colspan/rowspan) matching the actual document format.
 * Each table includes: title area, countersign column, info rows, column headers, data cells.
 */
import { useCallback, useRef } from 'react'
import type { TemplateSection } from '../../types/template'
import { getLayout } from './processDocumentLayouts'

interface Props {
  section: TemplateSection
  onChange: (section: TemplateSection) => void
}

const cellStyle: React.CSSProperties = {
  padding: '4px 8px',
  border: '1px solid #333',
  minHeight: 28,
  outline: 'none',
  fontSize: 13,
  lineHeight: 1.4,
  overflow: 'hidden',
  wordBreak: 'break-all',
}

const headerCellStyle: React.CSSProperties = {
  ...cellStyle,
  backgroundColor: '#e8e8e8',
  fontWeight: 600,
  textAlign: 'center',
  wordBreak: 'keep-all',
}

const titleCellStyle: React.CSSProperties = {
  ...cellStyle,
  backgroundColor: '#f5f5f5',
  fontWeight: 600,
  textAlign: 'center',
  fontSize: 14,
}

const titleValueCellStyle: React.CSSProperties = {
  ...cellStyle,
  backgroundColor: '#fafafa',
  fontSize: 13,
}

const infoCellStyle: React.CSSProperties = {
  ...cellStyle,
  backgroundColor: '#f8f8f8',
  fontWeight: 500,
  textAlign: 'center',
  fontSize: 12,
}

const ProcessTableEditor: React.FC<Props> = ({ section, onChange }) => {
  const tableRef = useRef<HTMLTableElement>(null)
  const chapterCode = section.section_id
  const layout = getLayout(chapterCode)

  // G19a flow chart — render as ordered step list
  if (chapterCode === 'G19a') {
    return <FlowChartEditor section={section} onChange={onChange} />
  }

  // No layout found — fallback to simple auto-generated table from data keys
  if (!layout) {
    return <FallbackTable section={section} onChange={onChange} />
  }

  const rows = section.rows || []
  const aiKeys = section.fill_sources
    ? new Set(section.fill_sources.unstructured || [])
    : new Set<string>()

  const handleBlur = useCallback(() => {
    if (!tableRef.current) return
    const keys = layout.dataColumns.map((c) => c.key)
    const newRows = parseTableToRows(tableRef.current, keys)
    onChange({ ...section, rows: newRows })
  }, [section, onChange, layout])

  const { titleRow0, titleRow1, infoRows, headerRows, dataColumns } = layout

  return (
    <div style={{ width: '100%' }}>
      <table
        ref={tableRef}
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          tableLayout: 'auto',
        }}
        onBlur={handleBlur}
      >
        <tbody>
          {/* Title Row 0: labels */}
          <tr>
            {titleRow0.map((cell, ci) => (
              <td
                key={ci}
                colSpan={cell.colspan}
                rowSpan={cell.rowspan}
                style={{
                  ...titleCellStyle,
                  fontSize: ci === 1 ? 16 : 14,
                }}
              >
                {cell.label}
              </td>
            ))}
          </tr>

          {/* Title Row 1: values (empty placeholders) */}
          <tr>
            {titleRow1.map((cell, ci) => (
              <td
                key={ci}
                colSpan={cell.colspan}
                rowSpan={cell.rowspan}
                style={titleValueCellStyle}
              >
                {cell.label}
              </td>
            ))}
          </tr>

          {/* Info rows (e.g. 材料/零件数量 for process cards) */}
          {infoRows && infoRows.map((row, ri) => (
            <tr key={`info-${ri}`}>
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  colSpan={cell.colspan}
                  rowSpan={cell.rowspan}
                  style={infoCellStyle}
                >
                  {cell.label}
                </td>
              ))}
            </tr>
          ))}

          {/* Column header rows */}
          {headerRows.map((row, ri) => (
            <tr key={`header-${ri}`}>
              {row.map((cell, ci) => (
                <th
                  key={ci}
                  colSpan={cell.colspan}
                  rowSpan={cell.rowspan}
                  style={{
                    ...headerCellStyle,
                    // Highlight countersign cell
                    ...(cell.label === '会签' ? {
                      writingMode: 'vertical-rl' as const,
                      letterSpacing: 4,
                      fontSize: 14,
                    } : {}),
                  }}
                >
                  {cell.label}
                </th>
              ))}
            </tr>
          ))}

          {/* Data rows */}
          {rows.length === 0 ? (
            <tr>
              {dataColumns.map((col, ci) => (
                <td
                  key={ci}
                  colSpan={col.colspan}
                  contentEditable
                  suppressContentEditableWarning
                  style={{
                    ...cellStyle,
                    color: '#bbb',
                  }}
                />
              ))}
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr key={ri}>
                {dataColumns.map((col, ci) => {
                  const isAI = aiKeys.has(col.key)
                  return (
                    <td
                      key={ci}
                      colSpan={col.colspan}
                      contentEditable
                      suppressContentEditableWarning
                      style={{
                        ...cellStyle,
                        backgroundColor: isAI ? '#e6f4ff' : undefined,
                        verticalAlign: 'top',
                      }}
                      title={isAI ? 'AI 生成内容' : undefined}
                    >
                      {String(row[col.key] ?? '')}
                    </td>
                  )
                })}
              </tr>
            ))
          )}

          {/* Signature row */}
          <SignatureRow totalCols={getTotalCols(layout)} />
        </tbody>
      </table>
    </div>
  )
}

/** Calculate total physical columns from layout */
function getTotalCols(layout: { titleRow0: { colspan?: number }[] }): number {
  return layout.titleRow0.reduce((sum, cell) => sum + (cell.colspan || 1), 0)
}

/** Signature row at bottom of every table */
const SignatureRow: React.FC<{ totalCols: number }> = ({ totalCols }) => (
  <tr>
    <td colSpan={totalCols} style={{ ...cellStyle, borderTop: '2px solid #333', padding: '6px 12px', fontSize: 12 }}>
      <span style={{ marginRight: 24 }}>编制:________</span>
      <span style={{ marginRight: 24 }}>审核:________</span>
      <span style={{ marginRight: 24 }}>校对:________</span>
      <span style={{ marginRight: 24 }}>标检:________</span>
      <span>批准:________</span>
    </td>
  </tr>
)

/** Fallback: auto-generate table from data row keys */
const FallbackTable: React.FC<{
  section: TemplateSection
  onChange: (section: TemplateSection) => void
}> = ({ section, onChange }) => {
  const rows = section.rows || []
  const keys =
    rows.length > 0 ? Object.keys(rows[0]) : section.column_keys || []

  if (keys.length === 0) {
    return <div style={{ color: '#888', padding: 12 }}>暂无数据</div>
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
        }}
      >
        <thead>
          <tr>
            {keys.map((key, i) => (
              <th key={i} style={headerCellStyle}>
                {key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {keys.map((key, ci) => (
                <td
                  key={ci}
                  contentEditable
                  suppressContentEditableWarning
                  style={cellStyle}
                >
                  {String(row[key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** G19a flow chart — ordered step list */
const FlowChartEditor: React.FC<{
  section: TemplateSection
  onChange: (section: TemplateSection) => void
}> = ({ section, onChange }) => {
  const steps = section.flow_steps || []

  if (steps.length === 0) {
    return <div style={{ color: '#888', padding: 12 }}>流程步骤暂无数据</div>
  }

  return (
    <ol style={{ paddingLeft: 20 }}>
      {steps.map((step, idx) => (
        <li key={idx} style={{ marginBottom: 6 }}>
          <span
            contentEditable
            suppressContentEditableWarning
            onBlur={(e) => {
              const updated = [...steps]
              updated[idx] = e.currentTarget.textContent || ''
              onChange({ ...section, flow_steps: updated })
            }}
            style={{
              padding: '2px 6px',
              border: '1px solid transparent',
              outline: 'none',
              display: 'inline-block',
              minWidth: 100,
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = '#1890ff'
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = 'transparent'
            }}
          >
            {step}
          </span>
        </li>
      ))}
    </ol>
  )
}

/** Parse HTML table rows back into data arrays */
function parseTableToRows(
  table: HTMLTableElement,
  keys: string[],
): Array<Record<string, unknown>> {
  const rows: Array<Record<string, unknown>> = []
  const trs = table.querySelectorAll('tbody tr')
  let dataStarted = false
  trs.forEach((tr) => {
    const cells = tr.querySelectorAll('td')
    if (!dataStarted) {
      const hasContentEditable = Array.from(cells).some(c => c.getAttribute('contenteditable') !== null)
      if (!hasContentEditable) return
      dataStarted = true
    }
    const row: Record<string, unknown> = {}
    let colIdx = 0
    keys.forEach((key) => {
      row[key] = cells[colIdx]?.textContent?.trim() || ''
      colIdx++
    })
    rows.push(row)
  })
  return rows
}

export default ProcessTableEditor
