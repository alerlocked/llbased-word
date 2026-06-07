/**
 * ExportButton — dropdown menu for PDF/Word/template PDF export
 *
 * Detects current editor content format and routes to the correct
 * export endpoint.
 */
import { useState } from 'react'
import { Button, Dropdown, message } from 'antd'
import { DownloadOutlined, FilePdfOutlined, FileWordOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { draftApi } from '../../services/draftApi'
import { useCreationStore } from '../../stores/creationStore'

const API_BASE = '/api/agent'

interface ExportButtonProps {
  draftId?: number
  projectId?: number
  style?: React.CSSProperties
}

const ExportButton: React.FC<ExportButtonProps> = ({ draftId, projectId, style }) => {
  const [loading, setLoading] = useState(false)
  const editorTemplateData = useCreationStore((s) => s.editorTemplateData)

  const handleExport = async (format: 'pdf' | 'word' | 'template-pdf') => {
    setLoading(true)
    try {
      if (format === 'template-pdf') {
        // Template-driven PDF export
        if (!editorTemplateData) {
          message.warning('无模板数据可导出')
          return
        }
        const res = await fetch(`${API_BASE}/export/template-pdf`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template_id: editorTemplateData.template_id,
            structured_doc: editorTemplateData,
            project_id: projectId,
          }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        // Download the blob
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${editorTemplateData.template_name || '工艺文件'}.pdf`
        a.click()
        URL.revokeObjectURL(url)
        message.success('模板 PDF 导出成功')
      } else if (format === 'pdf') {
        if (!draftId) {
          message.warning('请先上传或选择一个初稿')
          return
        }
        await draftApi.exportPdf(draftId)
        message.success('PDF 导出成功')
      } else {
        if (!draftId) {
          message.warning('请先上传或选择一个初稿')
          return
        }
        await draftApi.exportWord(draftId)
        message.success('Word 导出成功')
      }
    } catch (error) {
      console.error('导出失败:', error)
      message.error('导出失败')
    } finally {
      setLoading(false)
    }
  }

  const menuItems: MenuProps['items'] = [
    ...(editorTemplateData
      ? [
          {
            key: 'template-pdf',
            icon: <FilePdfOutlined />,
            label: '导出模板 PDF',
            onClick: () => handleExport('template-pdf'),
          },
        ]
      : []),
    {
      key: 'pdf',
      icon: <FilePdfOutlined />,
      label: '导出 PDF',
      onClick: () => handleExport('pdf'),
    },
    {
      key: 'word',
      icon: <FileWordOutlined />,
      label: '导出 Word',
      onClick: () => handleExport('word'),
    },
  ]

  return (
    <Dropdown menu={{ items: menuItems }} trigger={['click']}>
      <Button
        icon={<DownloadOutlined />}
        loading={loading}
        style={style}
      >
        导出
      </Button>
    </Dropdown>
  )
}

export default ExportButton
