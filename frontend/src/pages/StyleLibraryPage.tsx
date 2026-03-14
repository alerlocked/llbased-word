/**
 * StyleLibraryPage - 风格文章库管理页面
 * 管理用户风格文章的上传、查看、删除和训练
 */
import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Upload,
  Modal,
  message,
  Space,
  Tag,
  Input,
  Select,
  Statistic,
  Row,
  Col,
  Typography,
  Divider
} from 'antd'
import {
  UploadOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  RobotOutlined,
  FolderOpenOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import MainLayout from '../components/Layout/MainLayout'
import {
  getStyleArticles,
  getStyleStatistics,
  deleteStyleArticle,
  trainStyleModel,
  uploadStyleArticle,
  StyleArticle
} from '../services/styleService'

const { Text, Title, Paragraph } = Typography
const { TextArea } = Input

interface StyleProfile {
  user_id: number
  style_profile: any
  sample_count: number
  confidence_score: number
  last_updated: string
  update_count: number
}

interface Statistics {
  total_count: number
  trained_count: number
  untrained_count: number
  source_breakdown: {
    upload: number
    agent_generated: number
    editor_saved: number
  }
  total_words: number
}

const StyleLibraryPage: React.FC = () => {
  const [articles, setArticles] = useState<StyleArticle[]>([])
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<StyleProfile | null>(null)
  const [statistics, setStatistics] = useState<Statistics | null>(null)
  const [viewModalVisible, setViewModalVisible] = useState(false)
  const [selectedArticle, setSelectedArticle] = useState<StyleArticle | null>(null)
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined)
  const [trainedFilter, setTrainedFilter] = useState<boolean | undefined>(undefined)
  const [training, setTraining] = useState(false)
  const [viewProfileModalVisible, setViewProfileModalVisible] = useState(false)

  const userId = 1 // TODO: 从用户上下文获取

  // 获取文章列表
  const fetchArticles = async () => {
    setLoading(true)
    try {
      const articles = await getStyleArticles({
        user_id: userId,
        skip: 0,
        limit: 100,
        source: sourceFilter,
        is_trained: trainedFilter
      })
      setArticles(articles)
    } catch (error) {
      console.error('获取文章列表失败:', error)
      // 错误已在 apiClient 中处理
    } finally {
      setLoading(false)
    }
  }

  // 获取风格档案（暂时保留，如果后端有该接口）
  const fetchProfile = async () => {
    try {
      // TODO: 如果后端有 /style/profile/{user_id} 接口，使用 getStyleProfile
      // 目前先跳过，因为后端只有 /style/profiles?user_id=xxx
      // const profiles = await getStyleProfiles(userId)
      // if (profiles.length > 0) {
      //   setProfile(profiles[0])
      // }
    } catch (error) {
      console.error('获取风格档案失败:', error)
    }
  }

  // 获取统计信息
  const fetchStatistics = async () => {
    try {
      const stats = await getStyleStatistics(userId)
      setStatistics(stats)
    } catch (error) {
      console.error('获取统计信息失败:', error)
      // 错误已在 apiClient 中处理
    }
  }

  useEffect(() => {
    fetchArticles()
    fetchProfile()
    fetchStatistics()
  }, [sourceFilter, trainedFilter])

  // 上传文件配置
  const uploadProps = {
    name: 'file',
    accept: '.txt,.docx,.pdf',
    multiple: true,
    customRequest: async (options: any) => {
      const { file, onSuccess, onError } = options
      try {
        await uploadStyleArticle(file, userId)
        onSuccess?.(null, file)
        message.success(`${file.name} 上传成功`)
        fetchArticles()
        fetchStatistics()
      } catch (error: any) {
        const errorMsg = error.response?.data?.detail || error.message || '上传失败'
        message.error(`${file.name}: ${errorMsg}`)
        onError?.(error)
      }
    },
    onChange(info: any) {
      // 使用 customRequest 后，onChange 主要用于显示上传状态
      if (info.file.status === 'uploading') {
        // 上传中
      } else if (info.file.status === 'done') {
        // 已在 customRequest 中处理
      } else if (info.file.status === 'error') {
        // 已在 customRequest 中处理
      }
    }
  }

  // 上传文件夹配置
  const folderUploadProps = {
    ...uploadProps,
    directory: true,
  }

  // 删除文章
  const handleDelete = async (id: number) => {
    try {
      await deleteStyleArticle(id)
      message.success('文章已删除')
      fetchArticles()
      fetchStatistics()
    } catch (error) {
      console.error('删除文章失败:', error)
      // 错误已在 apiClient 中处理
    }
  }

  // 查看文章详情
  const handleView = (article: StyleArticle) => {
    setSelectedArticle(article)
    setViewModalVisible(true)
  }

  // 触发训练
  const handleTrain = async () => {
    setTraining(true)
    try {
      const result = await trainStyleModel(userId)
      message.success(result.message || '训练已启动')
      
      // 刷新数据
      setTimeout(() => {
        fetchArticles()
        fetchProfile()
        fetchStatistics()
      }, 2000)
    } catch (error) {
      console.error('训练失败:', error)
      // 错误已在 apiClient 中处理
    } finally {
      setTraining(false)
    }
  }

  // 来源标签
  const getSourceTag = (source: string) => {
    const sourceMap: Record<string, { color: string; text: string }> = {
      upload: { color: 'blue', text: '上传' },
      agent_generated: { color: 'green', text: 'Agent生成' },
      editor_saved: { color: 'orange', text: '编辑器保存' }
    }
    const config = sourceMap[source] || { color: 'default', text: source }
    return <Tag color={config.color}>{config.text}</Tag>
  }

  // 表格列定义
  const columns: ColumnsType<StyleArticle> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      width: 300
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (source: string) => getSourceTag(source),
      width: 120
    },
    {
      title: '字数',
      dataIndex: 'word_count',
      key: 'word_count',
      width: 100
    },
    {
      title: '训练状态',
      dataIndex: 'is_trained',
      key: 'is_trained',
      render: (trained: boolean) => (
        <Tag color={trained ? 'success' : 'default'}>
          {trained ? '已训练' : '未训练'}
        </Tag>
      ),
      width: 100
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
      width: 180
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: StyleArticle) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              Modal.confirm({
                title: '确认删除',
                content: '确定要删除这篇文章吗？',
                onOk: () => handleDelete(record.id)
              })
            }}
          >
            删除
          </Button>
        </Space>
      ),
      width: 150
    }
  ]

  return (
    <MainLayout>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px' }}>
        <Title level={2}>📚 风格文章库</Title>
        <Paragraph type="secondary">
          管理您的写作样本，系统会学习您的写作风格并应用到AI生成的文章中
        </Paragraph>

        {/* 统计信息 */}
        {statistics && (
          <Card style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic title="总文章数" value={statistics.total_count} />
              </Col>
              <Col span={6}>
                <Statistic
                  title="已训练"
                  value={statistics.trained_count}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="未训练"
                  value={statistics.untrained_count}
                  valueStyle={{ color: '#cf1322' }}
                />
              </Col>
              <Col span={6}>
                <Statistic title="总字数" value={statistics.total_words} />
              </Col>
            </Row>
          </Card>
        )}

        {/* 风格档案 */}
        {profile && (
          <Card 
            title="风格档案" 
            style={{ marginBottom: 24 }}
            extra={
              <Button type="link" onClick={() => setViewProfileModalVisible(true)}>
                查看详情
              </Button>
            }
          >
            <Row gutter={16}>
              <Col span={8}>
                <Text strong>样本数量：</Text>
                <Text>{profile.sample_count}</Text>
              </Col>
              <Col span={8}>
                <Text strong>置信度：</Text>
                <Text>{(profile.confidence_score * 100).toFixed(1)}%</Text>
              </Col>
              <Col span={8}>
                <Text strong>更新次数：</Text>
                <Text>{profile.update_count}</Text>
              </Col>
            </Row>
            <Divider />
            <Text type="secondary">
              最后更新：{new Date(profile.last_updated).toLocaleString('zh-CN')}
            </Text>
          </Card>
        )}

        {/* 操作栏 */}
        <Card style={{ marginBottom: 24 }}>
          <Space wrap>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />}>上传文件</Button>
            </Upload>

            <Upload {...folderUploadProps}>
              <Button icon={<FolderOpenOutlined />}>上传文件夹</Button>
            </Upload>
            
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={handleTrain}
              loading={training}
              disabled={!statistics || statistics.untrained_count === 0}
            >
              训练风格模型
            </Button>
            
            <Button icon={<ReloadOutlined />} onClick={fetchArticles}>
              刷新
            </Button>

            <Select
              style={{ width: 150 }}
              placeholder="筛选来源"
              allowClear
              value={sourceFilter}
              onChange={setSourceFilter}
            >
              <Select.Option value="upload">上传</Select.Option>
              <Select.Option value="agent_generated">Agent生成</Select.Option>
              <Select.Option value="editor_saved">编辑器保存</Select.Option>
            </Select>

            <Select
              style={{ width: 150 }}
              placeholder="训练状态"
              allowClear
              value={trainedFilter}
              onChange={setTrainedFilter}
            >
              <Select.Option value={true}>已训练</Select.Option>
              <Select.Option value={false}>未训练</Select.Option>
            </Select>
          </Space>
        </Card>

        {/* 文章列表 */}
        <Card>
          <Table
            columns={columns}
            dataSource={articles}
            rowKey="id"
            loading={loading}
            pagination={{
              pageSize: 20,
              showTotal: (total) => `共 ${total} 篇文章`
            }}
          />
        </Card>

        {/* 查看风格详情Modal */}
        <Modal
          title="风格档案详情"
          open={viewProfileModalVisible}
          onCancel={() => setViewProfileModalVisible(false)}
          footer={[
            <Button key="close" onClick={() => setViewProfileModalVisible(false)}>
              关闭
            </Button>
          ]}
          width={800}
        >
          {profile?.style_profile && (
            <div style={{ maxHeight: 600, overflow: 'auto' }}>
              <pre style={{ 
                background: '#f5f5f5', 
                padding: 16, 
                borderRadius: 4,
                border: '1px solid #d9d9d9',
                fontFamily: 'monospace',
                whiteSpace: 'pre-wrap',
                wordWrap: 'break-word'
              }}>
                {JSON.stringify(profile.style_profile, null, 2)}
              </pre>
            </div>
          )}
        </Modal>

        {/* 查看文章详情Modal */}
        <Modal
          title={selectedArticle?.title}
          open={viewModalVisible}
          onCancel={() => setViewModalVisible(false)}
          footer={[
            <Button key="close" onClick={() => setViewModalVisible(false)}>
              关闭
            </Button>
          ]}
          width={800}
        >
          {selectedArticle && (
            <div>
              <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
                <div>
                  <Text strong>来源：</Text>
                  {getSourceTag(selectedArticle.source)}
                </div>
                <div>
                  <Text strong>字数：</Text>
                  <Text>{selectedArticle.word_count}</Text>
                </div>
                <div>
                  <Text strong>训练状态：</Text>
                  <Tag color={selectedArticle.is_trained ? 'success' : 'default'}>
                    {selectedArticle.is_trained ? '已训练' : '未训练'}
                  </Tag>
                </div>
              </Space>
              <Divider />
              <div style={{ maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                {selectedArticle.content}
              </div>
            </div>
          )}
        </Modal>
      </div>
    </MainLayout>
  )
}

export default StyleLibraryPage