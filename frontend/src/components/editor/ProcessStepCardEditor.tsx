/**
 * ProcessStepCardEditor — Renders G25a process card steps
 * as expandable, editable card sections.
 *
 * Each card represents one process step with:
 * - Step number and name (editable)
 * - Content area (contentEditable div for rich text)
 * - Inspection checkpoints
 * - Auxiliary materials and instruments
 */
import { useCallback, useRef, useState } from 'react'
import { Collapse, Tag } from 'antd'
import type { TemplateSection } from '../../types/template'

interface Props {
  section: TemplateSection
  onChange: (section: TemplateSection) => void
}

const ProcessStepCardEditor: React.FC<Props> = ({ section, onChange }) => {
  const rows = section.rows || []
  const keys = section.column_keys || section.columns || []

  const handleFieldBlur = useCallback(
    (rowIdx: number, key: string, value: string) => {
      const next = [...rows]
      next[rowIdx] = { ...next[rowIdx], [key]: value }
      onChange({ ...section, rows: next })
    },
    [rows, section, onChange],
  )

  const collapseItems = rows.map((row, idx) => ({
    key: String(idx),
    label: (
      <span>
        <Tag color="blue">工序 {String(row.step_no ?? row.workshop ?? idx + 1)}</Tag>
        {String(row.step_name ?? `工序 ${idx + 1}`)}
      </span>
    ),
    children: (
      <ProcessCardFields
        row={row}
        keys={keys}
        onFieldBlur={(key, value) => handleFieldBlur(idx, key, value)}
      />
    ),
  }))

  if (rows.length === 0) {
    return <div style={{ color: '#888', padding: 12 }}>暂无工序数据</div>
  }

  return <Collapse items={collapseItems} defaultActiveKey={['0']} />
}

/** Individual card field renderer */
const ProcessCardFields: React.FC<{
  row: Record<string, unknown>
  keys: string[]
  onFieldBlur: (key: string, value: string) => void
}> = ({ row, keys, onFieldBlur }) => {
  // Separate short fields from long content fields
  const longKeys = new Set(['content', 'inspection', 'step_desc'])
  const shortFields = keys.filter((k) => !longKeys.has(k))
  const longFields = keys.filter((k) => longKeys.has(k))

  return (
    <div>
      {/* Short fields in a compact grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 8,
          marginBottom: 12,
        }}
      >
        {shortFields.map((key) => (
          <div key={key}>
            <label
              style={{
                fontSize: 12,
                color: '#888',
                display: 'block',
                marginBottom: 2,
              }}
            >
              {key}
            </label>
            <input
              type="text"
              defaultValue={String(row[key] ?? '')}
              onBlur={(e) => onFieldBlur(key, e.target.value)}
              style={{
                width: '100%',
                padding: '4px 8px',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                fontSize: 13,
                outline: 'none',
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = '#1890ff'
              }}
              onBlurCapture={(e) => {
                e.currentTarget.style.borderColor = '#d9d9d9'
              }}
            />
          </div>
        ))}
      </div>

      {/* Long content fields as contentEditable areas */}
      {longFields.map((key) => (
        <div key={key} style={{ marginBottom: 12 }}>
          <label
            style={{
              fontSize: 12,
              color: '#888',
              display: 'block',
              marginBottom: 4,
              fontWeight: 600,
            }}
          >
            {key === 'content' ? '工序内容' : key === 'inspection' ? '检验' : key}
          </label>
          <div
            contentEditable
            suppressContentEditableWarning
            onBlur={(e) => onFieldBlur(key, e.currentTarget.textContent || '')}
            style={{
              padding: 12,
              border: '1px solid #d9d9d9',
              borderRadius: 4,
              minHeight: 80,
              fontSize: 13,
              lineHeight: 1.6,
              outline: 'none',
              backgroundColor: '#fafafa',
              whiteSpace: 'pre-wrap',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = '#1890ff'
              e.currentTarget.style.backgroundColor = '#fff'
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = '#d9d9d9'
              e.currentTarget.style.backgroundColor = '#fafafa'
            }}
          >
            {String(row[key] ?? '')}
          </div>
        </div>
      ))}
    </div>
  )
}

export default ProcessStepCardEditor
