/**
 * ProcessTableEditor — Renders chapter data as proper process document tables.
 *
 * Uses layout definitions from processDocumentLayouts.ts to render tables
 * with grouped headers (colspan/rowspan) matching the actual document format.
 * Each table includes: title area, countersign column, info rows, column headers, data cells.
 */
import { useCallback, useRef, useState } from 'react'
import { Button, Tooltip } from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  ColumnHeightOutlined,
  BorderInnerOutlined,
} from '@ant-design/icons'
import type { CellMerge, TemplateSection } from '../../types/template'
import { getLayout } from './processDocumentLayouts'
import {
  cellStateFor,
  emptyRow,
  findMergeAt,
  mergeDown,
  removeRowFromMerges,
  shiftMerges,
  splitMerge,
} from './mergeUtils'

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
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
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
    const newRows = parseTableToRows(
      tableRef.current,
      keys,
      layout.dataColumns,
      section.merges,
    )
    onChange({ ...section, rows: newRows })
  }, [section, onChange, layout])

  const { titleRow0, titleRow1, infoRows, headerRows, dataColumns } = layout
  const colKeys = dataColumns.map((c) => c.key)

  // --- Row / merge operations (data-driven, then onChange) ---
  const addRowBelow = (rowIndex: number) => {
    const rows = [...(section.rows || [])]
    // If table was empty (placeholder row), replace with one real row
    if (rows.length === 0) {
      rows.push(emptyRow(colKeys))
    }
    rows.splice(rowIndex + 1, 0, emptyRow(colKeys))
    const merges = shiftMerges(section.merges, rowIndex + 1, +1)
    onChange({ ...section, rows, merges })
  }

  const deleteRow = (rowIndex: number) => {
    const rows = [...(section.rows || [])]
    if (rows.length <= rowIndex) return
    rows.splice(rowIndex, 1)
    const merges = removeRowFromMerges(section.merges, rowIndex)
    onChange({ ...section, rows, merges })
  }

  // --- Hover state ---
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)
  const [rowTop, setRowTop] = useState(0)
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: string } | null>(null)

  return (
    <div ref={containerRef} style={{ width: '100%', overflowX: 'auto', position: 'relative' }}>
      <table
        ref={tableRef}
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          tableLayout: 'fixed',
          minWidth: layout.colWidths.length > 16 ? `${layout.colWidths.length * 60}px` : undefined,
        }}
        onBlur={handleBlur}
      >
        <colgroup>
          {layout.colWidths.map((w, i) => (
            <col key={i} style={{ width: `${w}%` }} />
          ))}
        </colgroup>
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
            <tr
              onMouseEnter={(e) => {
                setHoveredRow(-1)
                setRowTop(e.currentTarget.offsetTop)
              }}
              onMouseLeave={() => setHoveredRow(null)}
            >
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
              <tr
                key={ri}
                data-row-index={ri}
                onMouseEnter={(e) => {
                  setHoveredRow(ri)
                  setRowTop(e.currentTarget.offsetTop)
                }}
                onMouseLeave={() => setHoveredRow(null)}
              >
                {dataColumns.map((col, ci) => {
                  const state = cellStateFor(section.merges, col.key, ri)
                  // Swallowed by a merge above — render nothing
                  if (state.kind === 'merged-out') return null
                  const isAI = aiKeys.has(col.key)
                  return (
                    <td
                      key={ci}
                      colSpan={col.colspan}
                      rowSpan={state.kind === 'merge-start' ? state.rowSpan : undefined}
                      contentEditable
                      suppressContentEditableWarning
                      onMouseEnter={() => setHoveredCell({ row: ri, col: col.key })}
                      onMouseLeave={() => setHoveredCell(null)}
                      style={{
                        ...cellStyle,
                        backgroundColor: isAI ? '#e6f4ff' : undefined,
                        verticalAlign: 'top',
                        whiteSpace: 'pre-wrap',
                        position: 'relative',
                      }}
                      title={isAI ? 'AI 生成内容' : undefined}
                    >
                      {String(row[col.key] ?? '')}
                      {hoveredCell?.row === ri && hoveredCell?.col === col.key && (
                        <CellMergeButton
                          section={section}
                          colKey={col.key}
                          rowIndex={ri}
                          rowCount={rows.length}
                          onChange={onChange}
                        />
                      )}
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

      {/* Row-level hover toolbar: add / delete row */}
      {hoveredRow !== null && (
        <div
          style={{
            position: 'absolute',
            top: rowTop,
            right: 4,
            display: 'flex',
            gap: 2,
            background: 'rgba(255,255,255,0.95)',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            padding: 2,
            boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
            zIndex: 10,
          }}
          onMouseDown={(e) => e.preventDefault()}
          onMouseEnter={() => setHoveredRow(hoveredRow)}
          onMouseLeave={() => setHoveredRow(null)}
        >
          <Tooltip title="在下方加一行">
            <Button
              size="small"
              type="text"
              icon={<PlusOutlined />}
              onClick={() => addRowBelow(hoveredRow < 0 ? -1 : hoveredRow)}
            />
          </Tooltip>
          {hoveredRow >= 0 && (
            <Tooltip title="删除此行">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => deleteRow(hoveredRow)}
              />
            </Tooltip>
          )}
        </div>
      )}
    </div>
  )
}

/** Calculate total physical columns from layout */
function getTotalCols(layout: { titleRow0: { colspan?: number }[] }): number {
  return layout.titleRow0.reduce((sum, cell) => sum + (cell.colspan || 1), 0)
}

/** Cell-level merge / split button shown on hover. */
const CellMergeButton: React.FC<{
  section: TemplateSection
  colKey: string
  rowIndex: number
  rowCount: number
  onChange: (s: TemplateSection) => void
}> = ({ section, colKey, rowIndex, rowCount, onChange }) => {
  const existing = findMergeAt(section.merges, colKey, rowIndex)
  const atBottom = rowIndex >= rowCount - 1
  const isMergeStart = existing && existing.startRow === rowIndex
  const mergeFull = isMergeStart && existing!.span >= rowCount - existing!.startRow

  const btn = (
    <Button
      size="small"
      type="text"
      icon={
        isMergeStart ? <BorderInnerOutlined /> : <ColumnHeightOutlined />
      }
      style={{
        position: 'absolute',
        top: 1,
        right: 1,
        padding: '0 4px',
        height: 18,
        fontSize: 12,
        background: 'rgba(255,255,255,0.9)',
      }}
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => {
        if (isMergeStart) {
          onChange(splitMerge(section, colKey, rowIndex))
        } else if (!atBottom && !mergeFull) {
          onChange(mergeDown(section, colKey, rowIndex, rowCount))
        }
      }}
    />
  )
  if (isMergeStart) {
    return <Tooltip title="拆分合并">{btn}</Tooltip>
  }
  if (atBottom) {
    return <Tooltip title="已是最后一行，无法向下合并">{btn}</Tooltip>
  }
  return <Tooltip title="与下方单元格合并">{btn}</Tooltip>
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
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)

  const addRowBelow = (rowIndex: number) => {
    const next = [...rows]
    if (next.length === 0) next.push(emptyRow(keys))
    next.splice(rowIndex + 1, 0, emptyRow(keys))
    onChange({ ...section, rows: next })
  }
  const deleteRow = (rowIndex: number) => {
    const next = [...rows]
    next.splice(rowIndex, 1)
    onChange({ ...section, rows: next })
  }

  if (keys.length === 0) {
    return <div style={{ color: '#888', padding: 12 }}>暂无数据</div>
  }

  return (
    <div style={{ overflowX: 'auto', position: 'relative' }}>
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
          {rows.length === 0 ? (
            <tr
              onMouseEnter={() => setHoveredRow(-1)}
              onMouseLeave={() => setHoveredRow(null)}
            >
              {keys.map((key, ci) => (
                <td
                  key={ci}
                  contentEditable
                  suppressContentEditableWarning
                  style={{ ...cellStyle, color: '#bbb' }}
                />
              ))}
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr
                key={ri}
                onMouseEnter={() => setHoveredRow(ri)}
                onMouseLeave={() => setHoveredRow(null)}
              >
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
            ))
          )}
        </tbody>
      </table>

      {/* Hover row toolbar */}
      {hoveredRow !== null && (
        <div
          style={{
            position: 'absolute',
            top: 'unset',
            bottom: 4,
            right: 4,
            display: 'flex',
            gap: 2,
            background: 'rgba(255,255,255,0.95)',
            border: '1px solid #d9d9d9',
            borderRadius: 4,
            padding: 2,
            boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
            zIndex: 10,
          }}
          onMouseDown={(e) => e.preventDefault()}
          onMouseEnter={() => setHoveredRow(hoveredRow)}
          onMouseLeave={() => setHoveredRow(null)}
        >
          <Tooltip title="在下方加一行">
            <Button
              size="small"
              type="text"
              icon={<PlusOutlined />}
              onClick={() => addRowBelow(hoveredRow < 0 ? -1 : hoveredRow)}
            />
          </Tooltip>
          {hoveredRow >= 0 && (
            <Tooltip title="删除此行">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => deleteRow(hoveredRow)}
              />
          </Tooltip>
          )}
        </div>
      )}
    </div>
  )
}

/** G19a flow chart — ordered step list */
const FlowChartEditor: React.FC<{
  section: TemplateSection
  onChange: (section: TemplateSection) => void
}> = ({ section, onChange }) => {
  const steps = section.flow_steps || []

  const addStep = (idx: number) => {
    const next = [...steps]
    next.splice(idx + 1, 0, '新步骤')
    onChange({ ...section, flow_steps: next })
  }
  const deleteStep = (idx: number) => {
    const next = [...steps]
    next.splice(idx, 1)
    onChange({ ...section, flow_steps: next })
  }

  if (steps.length === 0) {
    return (
      <div style={{ color: '#888', padding: 12 }}>
        流程步骤暂无数据
        <Tooltip title="添加第一个步骤">
          <Button
            size="small"
            type="text"
            icon={<PlusOutlined />}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => addStep(-1)}
          />
        </Tooltip>
      </div>
    )
  }

  return (
    <ol style={{ paddingLeft: 20 }}>
      {steps.map((step, idx) => (
        <li key={idx} style={{ marginBottom: 6, position: 'relative' }}>
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
          <span
            style={{ marginLeft: 8, display: 'inline-flex', gap: 2 }}
            onMouseDown={(e) => e.preventDefault()}
          >
            <Tooltip title="在下方加一步">
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                onClick={() => addStep(idx)}
              />
            </Tooltip>
            <Tooltip title="删除此步">
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => deleteStep(idx)}
              />
            </Tooltip>
          </span>
        </li>
      ))}
    </ol>
  )
}

/** Parse HTML table rows back into data arrays.
 *
 * `dataColumns` and `merges` mirror the render logic so that merged-out
 * cells (rendered as nothing) are read as empty strings and the DOM cell
 * index (`domIdx`) stays aligned with the rendered `<td>` sequence.
 */
function parseTableToRows(
  table: HTMLTableElement,
  keys: string[],
  dataColumns: Array<{ key: string }>,
  merges?: Record<string, CellMerge[]>,
): Array<Record<string, unknown>> {
  const rows: Array<Record<string, unknown>> = []
  const trs = table.querySelectorAll('tbody tr')
  let rowIndex = 0
  trs.forEach((tr) => {
    const cells = tr.querySelectorAll('td')
    // Only collect actual data rows: rows whose cells are contenteditable.
    // This skips title rows, info rows, header rows (th), and the signature row,
    // all of which come before/after data rows but must not be parsed as data.
    const hasContentEditable = Array.from(cells).some(
      (c) => c.getAttribute('contenteditable') !== null,
    )
    if (!hasContentEditable) return

    const row: Record<string, unknown> = {}
    let domIdx = 0
    dataColumns.forEach((col) => {
      const state = cellStateFor(merges, col.key, rowIndex)
      if (state.kind === 'merged-out') {
        row[col.key] = '' // swallowed cell
      } else {
        row[col.key] = cells[domIdx]?.textContent?.trim() || ''
        domIdx++
      }
    })
    rows.push(row)
    rowIndex++
  })
  return rows
}

export default ProcessTableEditor
