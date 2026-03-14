/**
 * PDFViewerDrawer - PDF查看抽屉
 */
import { useState, useEffect } from 'react'
import { Drawer, List, Empty, Spin, message } from 'antd'
import { EyeOutlined, FileTextOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

interface PDFDocument {
  id: string
  name: string
  page_count: number
}

interface PDFViewerDrawerProps {
  visible: boolean
  onClose: () => void
}

const PDFViewerDrawer: React.FC<PDFViewerDrawerProps> = ({
  visible,
  onClose
}) => {
  const [documents, setDocuments] = useState<PDFDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [_selectedDoc, setSelectedDoc] = useState<PDFDocument | null>(null)

  useEffect(() => {
    if (visible) {
      fetchDocuments()
    }
  }, [visible])

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/process-documents/')
      if (response.ok) {
        const data = await response.json()
        setDocuments(data.documents || [])
      }
    } catch (error) {
        message.error('获取文档列表失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Drawer
      title="PDF工艺文档"
      placement="right"
      width={500}
      onClose={onClose}
      open={visible}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : documents.length === 0 ? (
        <Empty description="暂无PDF文档" />
      ) : (
        <List
          dataSource={documents}
          renderItem={(doc: PDFDocument) => (
            <List.Item
              actions={[
                <a
                  key="view"
                  onClick={() => setSelectedDoc(doc)}
                  style={{ color: colors.primary }}
                >
                  <EyeOutlined />
                </a>
              ]}
            >
              <List.Item.Meta
                avatar={<FileTextOutlined style={{ fontSize: 24, color: colors.primary }} />}
                title={doc.name}
                description={`${doc.page_count} 页`}
              />
            </List.Item>
          )}
        />
      )}
    </Drawer>
  )
}

export default PDFViewerDrawer
