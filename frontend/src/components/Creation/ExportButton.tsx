/**
 * 导出按钮组件
 * 下拉菜单选择导出 PDF / Word
 */
import { useState } from 'react'
import { Button, Dropdown, message } from 'antd'
import { DownloadOutlined, FilePdfOutlined, FileWordOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { draftApi } from '../../services/draftApi'

interface ExportButtonProps {
  draftId?: number
  projectId?: number
  style?: React.CSSProperties
}

const ExportButton: React.FC<ExportButtonProps> = ({ draftId, projectId, style }) => {
  const [loading, setLoading] = useState(false)

  const handleExport = async (format: 'pdf' | 'word') => {
    if (!draftId) {
      message.warning('请先上传或选择一个初稿')
      return
    }

    setLoading(true)
    try {
      if (format === 'pdf') {
        await draftApi.exportPdf(draftId)
        message.success('PDF 导出成功')
      } else {
        await draftApi.exportWord(draftId)
        message.success('Word 导出成功')
      }
    } catch (error) {
      console.error('导出失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const menuItems: MenuProps['items'] = [
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
