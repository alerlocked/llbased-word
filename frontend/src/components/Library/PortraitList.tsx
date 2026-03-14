/**
 * PortraitList - 画像列表组件
 * 展示画像列表，支持搜索和筛选
 */
import { useState, useEffect } from 'react'
import { Card, Table, Button, Space, Tag, Input, Select, Typography, message, Modal } from 'antd'
import { 
  ReloadOutlined, 
  EyeOutlined, 
  EditOutlined, 
  DeleteOutlined,
  SearchOutlined 
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { getPortraitList, deleteStyleProfile, PortraitListItem } from '../../services/styleService'

const { Search } = Input
const { Text } = Typography

interface PortraitListProps {
  userId: number
  scenarioName?: string
  onView?: (portraitId: number) => void
  onEdit?: (portraitId: number) => void
  onRefresh?: () => void
}

export const PortraitList: React.FC<PortraitListProps> = ({
  userId,
  scenarioName,
  onView,
  onEdit,
  onRefresh
}) => {
  const [portraits, setPortraits] = useState<PortraitListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined)

  const fetchPortraits = async () => {
    setLoading(true)
    try {
      const response = await getPortraitList(userId, scenarioName)
      setPortraits(response.portraits)
    } catch (error) {
      console.error('获取画像列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPortraits()
  }, [userId, scenarioName])

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个画像吗？此操作不可恢复。',
      onOk: async () => {
        try {
          await deleteStyleProfile(id)
          message.success('删除成功')
          fetchPortraits()
          if (onRefresh) {
            onRefresh()
          }
        } catch (error) {
          console.error('删除失败:', error)
        }
      }
    })
  }

  const getSourceTag = (source: string) => {
    const sourceMap: Record<string, { color: string; text: string }> = {
      auto: { color: 'blue', text: '自动生成' },
      manual: { color: 'green', text: '手动创建' },
      hybrid: { color: 'orange', text: '混合' }
    }
    const config = sourceMap[source] || { color: 'default', text: source }
    return <Tag color={config.color}>{config.text}</Tag>
  }

  // 过滤数据
  const filteredPortraits = portraits.filter(portrait => {
    const matchSearch = !searchText || 
      portrait.summary.toLowerCase().includes(searchText.toLowerCase()) ||
      portrait.scenario_name?.toLowerCase().includes(searchText.toLowerCase())
    const matchSource = !sourceFilter || portrait.source === sourceFilter
    return matchSearch && matchSource
  })

  const columns: ColumnsType<PortraitListItem> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80
    },
    {
      title: '业务场景',
      dataIndex: 'scenario_name',
      key: 'scenario_name',
      width: 150,
      render: (name) => name || <Text type="secondary">默认</Text>
    },
    {
      title: '风格概述',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
      width: 300
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
      render: (version) => `v${version}`
    },
    {
      title: '置信度',
      dataIndex: 'confidence_score',
      key: 'confidence_score',
      width: 120,
      render: (score) => (
        <Tag color={score >= 0.8 ? 'green' : score >= 0.6 ? 'orange' : 'red'}>
          {(score * 100).toFixed(1)}%
        </Tag>
      ),
      sorter: (a, b) => a.confidence_score - b.confidence_score
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 120,
      render: (source) => getSourceTag(source),
      filters: [
        { text: '自动生成', value: 'auto' },
        { text: '手动创建', value: 'manual' },
        { text: '混合', value: 'hybrid' }
      ],
      onFilter: (value, record) => record.source === value
    },
    {
      title: '更新时间',
      dataIndex: 'last_updated',
      key: 'last_updated',
      width: 180,
      render: (date) => date ? new Date(date).toLocaleString('zh-CN') : '-',
      sorter: (a, b) => {
        const dateA = a.last_updated ? new Date(a.last_updated).getTime() : 0
        const dateB = b.last_updated ? new Date(b.last_updated).getTime() : 0
        return dateA - dateB
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_: any, record: PortraitListItem) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => onView && onView(record.id)}
          >
            查看
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => onEdit && onEdit(record.id)}
          >
            编辑
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      )
    }
  ]

  return (
    <Card
      title="画像列表"
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={fetchPortraits}
          loading={loading}
        >
          刷新
        </Button>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Space wrap>
          <Search
            placeholder="搜索画像（场景名称或风格概述）"
            allowClear
            style={{ width: 300 }}
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={fetchPortraits}
          />
          <Select
            style={{ width: 150 }}
            placeholder="筛选来源"
            allowClear
            value={sourceFilter}
            onChange={setSourceFilter}
          >
            <Select.Option value="auto">自动生成</Select.Option>
            <Select.Option value="manual">手动创建</Select.Option>
            <Select.Option value="hybrid">混合</Select.Option>
          </Select>
        </Space>

        <Table
          columns={columns}
          dataSource={filteredPortraits}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            pageSize: 20,
            showTotal: (total) => `共 ${total} 个画像`,
            showSizeChanger: true
          }}
        />
      </Space>
    </Card>
  )
}

export default PortraitList
