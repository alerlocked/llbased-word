/**
 * TemplateContentEditor — Main template-driven editor component
 *
 * Renders structured template data as editable tables/cards.
 * Each chapter is rendered by a sub-component based on its table_type.
 */
import { useCallback } from 'react'
import { Empty, Typography } from 'antd'
import type { TemplateSection } from '../../types/template'
import ChapterTableEditor from './ChapterTableEditor'
import ProcessStepCardEditor from './ProcessStepCardEditor'

const { Title } = Typography

interface Props {
  sections: TemplateSection[]
  onChange: (sections: TemplateSection[]) => void
}

const TemplateContentEditor: React.FC<Props> = ({ sections, onChange }) => {
  const handleSectionChange = useCallback(
    (index: number, updated: TemplateSection) => {
      const next = [...sections]
      next[index] = updated
      onChange(next)
    },
    [sections, onChange],
  )

  if (!sections || sections.length === 0) {
    return <Empty description="暂无模板数据" />
  }

  return (
    <div style={{ padding: '16px 24px' }}>
      {sections.map((section, idx) => (
        <div
          key={section.section_id}
          style={{ marginBottom: 32 }}
        >
          <Title level={4} style={{ marginBottom: 12 }}>
            {section.title}
          </Title>

          {section.content_type === 'table' && section.table_type === 'process_card' ? (
            <ProcessStepCardEditor
              section={section}
              onChange={(s) => handleSectionChange(idx, s)}
            />
          ) : section.content_type === 'table' || section.content_type === 'dual_table' ? (
            <ChapterTableEditor
              section={section}
              onChange={(s) => handleSectionChange(idx, s)}
            />
          ) : section.content_type === 'flow_chart' ? (
            <FlowChartEditor
              section={section}
              onChange={(s) => handleSectionChange(idx, s)}
            />
          ) : (
            <div style={{ color: '#888' }}>
              未知内容类型: {section.content_type}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

/** Simple flow chart editor — ordered step list with editable text */
const FlowChartEditor: React.FC<{
  section: TemplateSection
  onChange: (s: TemplateSection) => void
}> = ({ section, onChange }) => {
  const steps = section.flow_steps || []

  const handleStepChange = (index: number, value: string) => {
    const updated = [...steps]
    updated[index] = value
    onChange({ ...section, flow_steps: updated })
  }

  return (
    <ol style={{ paddingLeft: 20 }}>
      {steps.map((step, idx) => (
        <li key={idx} style={{ marginBottom: 6 }}>
          <span
            contentEditable
            suppressContentEditableWarning
            onBlur={(e) => handleStepChange(idx, e.currentTarget.textContent || '')}
            style={{
              padding: '2px 6px',
              borderRadius: 4,
              border: '1px solid transparent',
              outline: 'none',
              minWidth: 100,
              display: 'inline-block',
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

export default TemplateContentEditor
