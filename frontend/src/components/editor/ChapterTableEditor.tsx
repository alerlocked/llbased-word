/**
 * ChapterTableEditor — Renders single_row_list and dual_list chapters
 * as editable HTML tables.
 *
 * - Header row: locked (grey background)
 * - Data rows: contentEditable cells
 * - Changes propagate upward on blur
 */
import { useCallback, useRef } from 'react'
import type { TemplateSection } from '../../types/template'

interface Props {
  section: TemplateSection
  /** Set of column keys that are LLM-generated (unstructured) */
  aiGeneratedKeys?: Set<string>
  onChange: (section: TemplateSection) => void
}

const ChapterTableEditor: React.FC<Props> = ({ section, aiGeneratedKeys, onChange }) => {
  const tableRef = useRef<HTMLTableElement>(null)

  const handleBlur = useCallback(() => {
    if (!tableRef.current) return

    if (section.content_type === 'dual_table') {
      // Parse left and right tables
      const leftTable = tableRef.current.querySelector('.dual-left table') as HTMLTableElement
      const rightTable = tableRef.current.querySelector('.dual-right table') as HTMLTableElement
      const leftKeys = section.left_columns || []
      const rightKeys = section.right_columns || []

      const leftData = parseTableToRows(leftTable, leftKeys)
      const rightData = parseTableToRows(rightTable, rightKeys)

      onChange({
        ...section,
        left_data: leftData,
        right_data: rightData,
      })
    } else {
      // Single table
      const keys = section.column_keys || []
      const rows = parseTableToRows(tableRef.current, keys)
      onChange({ ...section, rows })
    }
  }, [section, onChange])

  if (section.content_type === 'dual_table') {
    return (
      <div ref={tableRef as React.RefObject<HTMLDivElement>} className="dual-table-editor" onBlur={handleBlur}>
        <div style={{ display: 'flex', gap: 16 }}>
          <div className="dual-left" style={{ flex: 1 }}>
            <h5>{section.left_columns?.join(' / ') || '左侧'}</h5>
            {renderDualTable(
              section.left_columns || [],
              section.left_data || [],
            )}
          </div>
          <div className="dual-right" style={{ flex: 1 }}>
            <h5>{section.right_columns?.join(' / ') || '右侧'}</h5>
            {renderDualTable(
              section.right_columns || [],
              section.right_data || [],
            )}
          </div>
        </div>
      </div>
    )
  }

  // Plain-text chapters (source-visibility REF appendix): read-only block.
  // Provenance info only — not editable, never part of feedback diff.
  if (section.content_type === 'text') {
    const text = section.field_values?.content
    if (typeof text === 'string' && text.trim()) {
      return (
        <div
          style={{
            whiteSpace: 'pre-wrap',
            fontSize: 14,
            lineHeight: 1.8,
            padding: '8px 4px',
            color: '#444',
          }}
        >
          {text}
        </div>
      )
    }
    return null
  }

  // Standard single table
  const columns = section.columns || []
  const rows = section.rows || []
  const keys = section.column_keys || columns
  // Build AI-generated key set from fill_sources if not provided via props
  const aiKeys = aiGeneratedKeys ?? (
    section.fill_sources
      ? new Set(section.fill_sources.unstructured || [])
      : new Set<string>()
  )

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        ref={tableRef}
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: 14,
        }}
        onBlur={handleBlur}
      >
        <thead>
          <tr>
            {columns.map((col, idx) => (
              <th
                key={idx}
                style={{
                  padding: '8px 12px',
                  backgroundColor: '#f5f5f5',
                  border: '1px solid #d9d9d9',
                  textAlign: 'left',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {keys.map((key, colIdx) => (
                <td
                  key={colIdx}
                  contentEditable
                  suppressContentEditableWarning
                  style={{
                    padding: '6px 12px',
                    border: '1px solid #d9d9d9',
                    minHeight: 32,
                    outline: 'none',
                    backgroundColor: aiKeys.has(key) ? '#e6f4ff' : undefined,
                  }}
                  title={aiKeys.has(key) ? 'AI 生成内容' : undefined}
                  onFocus={(e) => {
                    e.currentTarget.style.backgroundColor = '#bae0ff'
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.backgroundColor = aiKeys.has(key) ? '#e6f4ff' : ''
                  }}
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

function renderDualTable(
  columns: string[],
  rows: Array<Record<string, unknown>>,
) {
  return (
    <table
      style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: 14,
      }}
    >
      <thead>
        <tr>
          {columns.map((col, idx) => (
            <th
              key={idx}
              style={{
                padding: '8px 12px',
                backgroundColor: '#f5f5f5',
                border: '1px solid #d9d9d9',
                textAlign: 'left',
                fontWeight: 600,
              }}
            >
              {col}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIdx) => (
          <tr key={rowIdx}>
            {columns.map((col, colIdx) => (
              <td
                key={colIdx}
                contentEditable
                suppressContentEditableWarning
                style={{
                  padding: '6px 12px',
                  border: '1px solid #d9d9d9',
                  outline: 'none',
                }}
              >
                {String(row[col] ?? '')}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Parse HTML table rows back into data arrays */
function parseTableToRows(
  table: HTMLTableElement | null,
  keys: string[],
): Array<Record<string, unknown>> {
  if (!table) return []
  const rows: Array<Record<string, unknown>> = []
  const trs = table.querySelectorAll('tbody tr')
  trs.forEach((tr) => {
    const cells = tr.querySelectorAll('td')
    const row: Record<string, unknown> = {}
    keys.forEach((key, idx) => {
      row[key] = cells[idx]?.textContent?.trim() || ''
    })
    rows.push(row)
  })
  return rows
}

export default ChapterTableEditor
