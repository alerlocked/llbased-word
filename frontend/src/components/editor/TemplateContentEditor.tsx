/**
 * TemplateContentEditor — Main template-driven editor component
 *
 * Renders structured template data as editable tables.
 * Uses ProcessTableEditor for proper process document table layout.
 */
import { useCallback } from 'react'
import { Empty, Typography } from 'antd'
import type { TemplateSection } from '../../types/template'
import ProcessTableEditor from './ProcessTableEditor'

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
    <div style={{ padding: '8px 4px' }}>
      {sections.map((section, idx) => (
        <div
          key={section.section_id}
          style={{ marginBottom: 32 }}
        >
          <Title level={4} style={{ marginBottom: 12 }}>
            {section.title}
          </Title>

          <ProcessTableEditor
            section={section}
            onChange={(s) => handleSectionChange(idx, s)}
          />
        </div>
      ))}
    </div>
  )
}

export default TemplateContentEditor
