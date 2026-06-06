/**
 * EditorPanel — unified template-driven editor
 *
 * All content is rendered as structured tables via TemplateContentEditor.
 * No Tiptap / HtmlTableEditor fallback.
 */
import { useEffect, useRef, useState } from 'react'
import { Upload, Button, message, Empty } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'
import { draftApi } from '../../services/draftApi'
import ExportButton from './ExportButton'
import TemplateContentEditor from '../editor/TemplateContentEditor'
import { useCreationStore } from '../../stores/creationStore'
import type { TemplateSection } from '../../types/template'

interface EditorPanelProps {
  content: string
  onChange: (content: string) => void
  onContextMenu?: (event: React.MouseEvent, selectedText: string) => void
  placeholder?: string
  projectId?: number
}

const EditorPanel: React.FC<EditorPanelProps> = ({
  onChange,
  projectId
}) => {
  const { colors } = useTheme()
  const [currentDraftId, setCurrentDraftId] = useState<number | undefined>(undefined)
  const [uploading, setUploading] = useState(false)

  // Template editor state
  const editorTemplateData = useCreationStore((s) => s.editorTemplateData)
  const [templateSections, setTemplateSections] = useState<TemplateSection[]>([])

  // Convert ChapterData[] to TemplateSection[]
  useEffect(() => {
    if (editorTemplateData) {
      const sections: TemplateSection[] = editorTemplateData.chapters.map((ch) => ({
        section_id: ch.chapter_code,
        title: ch.chapter_title,
        content_type: mapTableType(ch.table_type),
        columns: [],
        column_keys: [],
        rows: ch.filled_data || [],
        left_data: ch.left_data,
        right_data: ch.right_data,
        flow_steps: ch.flow_steps,
        field_values: ch.field_values,
        review_passed: true,
        source: 'template_generated',
        table_type: ch.table_type,
      }))
      setTemplateSections(sections)
    } else {
      setTemplateSections([])
    }
  }, [editorTemplateData])

  const handleUploadDraft = async (file: File) => {
    setUploading(true)
    try {
      const result = await draftApi.uploadDraft(file, projectId)
      setCurrentDraftId(result.id)
      message.success(`初稿「${result.title}」上传成功`)
    } catch (error) {
      console.error('上传初稿失败:', error)
    } finally {
      setUploading(false)
    }
    return false
  }

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: colors.bgPrimary,
        overflow: 'hidden'
      }}
    >
      {/* Toolbar */}
      <div style={{
        padding: '12px 24px',
        borderBottom: `1px solid ${colors.borderColor}`,
        backgroundColor: colors.bgSecondary,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <Upload
            accept=".pdf"
            showUploadList={false}
            beforeUpload={(file) => { handleUploadDraft(file); return false }}
          >
            <Button
              icon={<UploadOutlined />}
              loading={uploading}
              size="small"
            >
              上传初稿
            </Button>
          </Upload>
        </div>
        <ExportButton draftId={currentDraftId} projectId={projectId} />
      </div>

      {/* Editor area */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {templateSections.length > 0 ? (
          <TemplateContentEditor
            sections={templateSections}
            onChange={(sections) => {
              setTemplateSections(sections)
              // Serialize back for auto-save consumers
              onChange(JSON.stringify(sections))
            }}
          />
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}>
            <Empty description="上传初稿后，AI 将自动生成结构化表格内容" />
          </div>
        )}
      </div>
    </div>
  )
}

function mapTableType(tableType: string): TemplateSection['content_type'] {
  const mapping: Record<string, TemplateSection['content_type']> = {
    single_row_list: 'table',
    process_card: 'table',
    dual_list: 'dual_table',
    flow_chart: 'flow_chart',
    fields: 'fields',
  }
  return mapping[tableType] || 'text'
}

export default EditorPanel
