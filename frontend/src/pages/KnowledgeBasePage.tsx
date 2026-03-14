/**
 * KnowledgeBasePage - RAG知识库管理页面
 * 管理向量知识库的文档上传、同步和查看
 */
import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Upload,
  message,
  Space,
  Tag,
  Select,
  Statistic,
  Row,
  Col,
  Typography,
  Modal,
  Tabs
} from 'antd'
import {
  UploadOutlined,
  DeleteOutlined,
  SyncOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  EditOutlined,
  FolderOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import MainLayout from '../components/Layout/MainLayout'

const { Text, Title, Paragraph } = Typography
const { TabPane } = Tabs

interface RAGDocument {
  doc_id: string
  doc_type: string
  metadata: any
  chunk_count: number
}

interface RAGStatistics {
  status: string
  total_documents: number
  total_chunks: number
  doc_type_breakdown?: Record<string, number>
}

const KnowledgeBasePage: React.FC = () => {
  const [documents, setDocuments] = useState<RAGDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [statistics, setStatistics] = useState<RAGStatistics | null>(null)
  const [docTypeFilter, setDocTypeFilter] = useState<string | undefined>(undefined)
  const [syncing, setSyncing] = useState(false)

  // 获取文档列表
  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '100' })
      if (docTypeFilter) params.append('doc_type', docTypeFilter)

      const response = await fetch(`http://localhost:8000/api/rag/documents?${params}`)
      if (response.ok) {
        const data = await response.json()
        setDocuments(data.documents || [])
      } else {
        message.error('获取文档列表失败')
      }
    } catch (error) {
      console.error('获取文档列表失败:', error)
      message.error('网络错误')
    } finally {
      setLoading(false)
    }
  }

  // 获取统计信息
  const fetchStatistics = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/rag/statistics')
      if (response.ok) {
        const data = await response.json()
        setStatistics(data)
      }
    } catch (error) {
      console.error('获取统计信息失败:', error)
    }
  }

  useEffect(() => {
    fetchDocuments()
    fetchStatistics()
  }, [docTypeFilter])

  // 上传文档配置
  const uploadProps = {
    name: 'file',
    action: 'http://localhost:8000/api/rag/upload-document',
    accept: '.txt,.docx,.pdf',
    onChange(info: any) {
      if (info.file.status === 'done') {
        message.success(`${info.file.name} 上传成功`)
        fetchDocuments()
        fetchStatistics()
      } else if (info.file.status === 'error') {
        message.error(`${info.file.name} 上传失败`)
      }
    }
  }

  // 同步数据到RAG
  const handleSync = async (syncType: string) => {
    setSyncing(true)
    try {
      const response = await fetch('http://localhost:8000/api/rag/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sync_type: syncType })
      })

      if (response.ok) {
        const data = await response.json()
        message.success(data.message)

        // 延迟刷新，等待同步完成
        setTimeout(() => {
          fetchDocuments()
          fetchStatistics()
        }, 3000)
      } else {
        message.error('同步启动失败')
      }
    } catch (error) {
      console.error('同步失败:', error)
      message.error('网络错误')
    } finally {
      setSyncing(false)
    }
  }

  // 删除文档
  const handleDelete = async (docId: string) => {
    try {
      const response = await fetch('http://localhost:8000/api/rag/document', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId })
      })

      if (response.ok) {
        message.success('文档已删除')
        fetchDocuments()
        fetchStatistics()
      } else {
        message.error('删除失败')
      }
    } catch (error) {
      console.error('删除文档失败:', error)
      message.error('网络错误')
    }
  }

  // 文档类型标签
  const getDocTypeTag = (docType: string) => {
    const typeMap: Record<string, { color: string; text: string; icon: any }> = {
      document: { color: 'green', text: '文档', icon: <FileTextOutlined /> },
      article: { color: 'blue', text: '文章', icon: <EditOutlined /> },
      project: { color: 'orange', text: '项目', icon: <FolderOutlined /> },
      uploaded_document: { color: 'purple', text: '上传文档', icon: <UploadOutlined /> }
    }
    const config = typeMap[docType] || { color: 'default', text: docType, icon: null }
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    )
  }

  // 表格列定义
  const columns: ColumnsType<RAGDocument> = [
    {
      title: '文档ID',
      dataIndex: 'doc_id',
      key: 'doc_id',
      ellipsis: true,
      width: 250
    },
    {
      title: '类型',
      dataIndex: 'doc_type',
      key: 'doc_type',
      render: (type: string) => getDocTypeTag(type),
      width: 120
    },
    {
      title: '文本块数量',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 120
    },
    {
      title: '元数据',
      dataIndex: 'metadata',
      key: 'metadata',
      render: (metadata: any) => (
        <div style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {metadata.filename || metadata.title || metadata.project_name || '-'}
        </div>
      ),
      ellipsis: true
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: RAGDocument) => (
        <Button
          type="link"
          danger
          icon={<DeleteOutlined />}
          onClick={() => {
            Modal.confirm({
              title: '确认删除',
              content: '确定要从知识库中删除这个文档吗？',
              onOk: () => handleDelete(record.doc_id)
            })
          }}
        >
          删除
        </Button>
      ),
      width: 100
    }
  ]

  return (
    <MainLayout>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px' }}>
        <Title level={2}>🗄️ RAG知识库管理</Title>
        <Paragraph type="secondary">
          管理向量知识库，系统会从这里检索相关信息来辅助AI生成工艺文件
        </Paragraph>

        {/* 统计信息 */}
        {statistics && (
          <Card style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="服务状态"
                  value={statistics.status}
                  valueStyle={{
                    color: statistics.status === '正常' ? '#3f8600' : '#cf1322'
                  }}
                />
              </Col>
              <Col span={6}>
                <Statistic title="文档数量" value={statistics.total_documents} />
              </Col>
              <Col span={6}>
                <Statistic title="文本块数量" value={statistics.total_chunks} />
              </Col>
              <Col span={6}>
                <Statistic
                  title="存储大小"
                  value={Math.round(statistics.total_chunks * 0.5)}
                  suffix="KB"
                />
              </Col>
            </Row>

            {statistics.doc_type_breakdown && (
              <div style={{ marginTop: 16 }}>
                <Text strong>文档类型分布：</Text>
                <Space style={{ marginLeft: 16 }}>
                  {Object.entries(statistics.doc_type_breakdown).map(([type, count]) => (
                    <Tag key={type}>
                      {type}: {count}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}
          </Card>
        )}

        {/* 操作栏 */}
        <Card style={{ marginBottom: 24 }}>
          <Tabs defaultActiveKey="upload">
            <TabPane tab="上传文档" key="upload">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Paragraph>
                  上传参考文档到知识库，支持TXT、Word、PDF格式
                </Paragraph>
                <Upload {...uploadProps}>
                  <Button icon={<UploadOutlined />} type="primary">
                    上传参考文档
                  </Button>
                </Upload>
              </Space>
            </TabPane>

            <TabPane tab="同步数据" key="sync">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Paragraph>
                  将系统中的文档、文章、项目内容同步到知识库
                </Paragraph>
                <Space wrap>
                  <Button
                    icon={<SyncOutlined />}
                    onClick={() => handleSync('articles')}
                    loading={syncing}
                  >
                    同步文章
                  </Button>
                  <Button
                    icon={<SyncOutlined />}
                    onClick={() => handleSync('projects')}
                    loading={syncing}
                  >
                    同步项目内容
                  </Button>
                  <Button
                    type="primary"
                    icon={<DatabaseOutlined />}
                    onClick={() => handleSync('all')}
                    loading={syncing}
                  >
                    全量同步
                  </Button>
                </Space>
              </Space>
            </TabPane>
          </Tabs>
        </Card>

        {/* 文档列表 */}
        <Card
          title="知识库文档"
          extra={
            <Space>
              <Select
                style={{ width: 150 }}
                placeholder="筛选类型"
                allowClear
                value={docTypeFilter}
                onChange={setDocTypeFilter}
              >
                <Select.Option value="document">文档</Select.Option>
                <Select.Option value="article">文章</Select.Option>
                <Select.Option value="project">项目</Select.Option>
                <Select.Option value="uploaded_document">上传文档</Select.Option>
              </Select>
              <Button
                icon={<SyncOutlined />}
                onClick={() => {
                  fetchDocuments()
                  fetchStatistics()
                }}
              >
                刷新
              </Button>
            </Space>
          }
        >
          <Table
            columns={columns}
            dataSource={documents}
            rowKey="doc_id"
            loading={loading}
            pagination={{
              pageSize: 20,
              showTotal: (total) => `共 ${total} 个文档`
            }}
          />
        </Card>
      </div>
    </MainLayout>
  )
}

export default KnowledgeBasePage
