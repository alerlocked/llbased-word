/**
 * AddMaterialDialog - 添加素材对话框（通用组件）
 * 支持两种使用模式：
 * 1. 回调模式：通过onConfirm返回选中的IDs
 * 2. 自动添加模式：通过projectId自动添加到项目
 */
import { useState, useEffect } from 'react'
import { Modal, Table, Input, message, Tag, Empty, Button } from 'antd'
import { SearchOutlined, UploadOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'

interface MaterialRecord {
  id: number
  name: string
  type: string
  created_at: string
  folder_id: number | null
}

interface AddMaterialDialogProps {
  visible: boolean
  onCancel: () => void
  // 回调模式：返回选中的IDs
  onConfirm?: (selectedIds: number[]) => void
  // 自动添加模式：自动添加到项目
  projectId?: number | null
  onSuccess?: () => void
  // 可选：已存在的素材ID列表（用于显示"已添加"标签）
  existingMaterialIds?: number[]
}

const AddMaterialDialog: React.FC<AddMaterialDialogProps> = ({
  visible,
  onCancel,
  onConfirm,
  projectId,
  onSuccess,
  existingMaterialIds = []
}) => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [materials, setMaterials] = useState<MaterialRecord[]>([])
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [searchText, setSearchText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // N4: folder id -> name map for grouping + group-select
  const [folderNames, setFolderNames] = useState<Record<number, string>>({})

  // Load folder tree and flatten to id -> name
  const loadFolderNames = async () => {
    interface FolderNode {
      id: number
      name: string
      children?: FolderNode[]
    }
    const flatten = (nodes: FolderNode[], map: Record<number, string>) => {
      nodes.forEach(n => {
        map[n.id] = n.name
        if (n.children) flatten(n.children, map)
      })
    }
    try {
      const resp = await fetch('http://localhost:8000/api/creation/material-folders')
      if (resp.ok) {
        const map: Record<number, string> = {}
        flatten((await resp.json()) as FolderNode[], map)
        setFolderNames(map)
      }
    } catch {
      console.error('获取文件夹失败')
    }
  }

  // 判断使用哪种模式
  const isCallbackMode = !!onConfirm
  const isAutoAddMode = !!projectId && !onConfirm

  // 获取素材列表
  useEffect(() => {
    if (visible) {
      fetchMaterials()
      loadFolderNames()
      setSelectedRowKeys([])
    }
  }, [visible])

  const fetchMaterials = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/creation/materials')
      if (response.ok) {
        const data = await response.json()
        setMaterials(data.items || [])
      } else {
        message.error('获取素材列表失败')
      }
    } catch (error) {
      message.error('网络错误')
      console.error('获取素材列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 格式化日期
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN')
  }

  // 类型标签
  const getTypeTag = (type: string) => {
    const typeMap: Record<string, { color: string; text: string }> = {
      pdf: { color: 'red', text: 'PDF' },
      docx: { color: 'blue', text: 'Word' },
      txt: { color: 'default', text: 'TXT' },
      document: { color: 'green', text: '文档' }
    }
    const config = typeMap[type] || { color: 'default', text: type }
    return <Tag color={config.color}>{config.text}</Tag>
  }

  // 表格列定义
  const columns: ColumnsType<MaterialRecord> = [
    {
      title: '素材名称',
      dataIndex: 'name',
      key: 'name',
      filteredValue: searchText ? [searchText] : null,
      onFilter: (value, record) =>
        record.name.toLowerCase().includes((value as string).toLowerCase()),
      render: (text, record) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined style={{ color: '#1890ff' }} />
          <div>
            <div style={{ fontWeight: 500 }}>{text}</div>
            {existingMaterialIds.includes(record.id) && (
              <Tag color="green" style={{ marginTop: 4 }}>已添加</Tag>
            )}
          </div>
        </div>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: getTypeTag
    },
    {
      title: '文件夹',
      dataIndex: 'folder_id',
      key: 'folder_id',
      width: 150,
      render: (folderId: number | null) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>{folderId != null ? (folderNames[folderId] || `#${folderId}`) : '未分组'}</span>
          <Button
            size="small"
            type="link"
            style={{ padding: 0 }}
            onClick={() => handleSelectFolder(folderId)}
          >
            全选
          </Button>
        </div>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: formatDate,
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend' as const
    }
  ]

  // 行选择配置
  const rowSelection = {
    selectedRowKeys,
    onChange: (selectedKeys: React.Key[]) => {
      setSelectedRowKeys(selectedKeys)
    },
    getCheckboxProps: (record: MaterialRecord) => ({
      disabled: existingMaterialIds.includes(record.id),
      name: record.name
    })
  }

  // 确认添加（回调模式）
  const handleConfirm = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请至少选择一个素材')
      return
    }
    if (onConfirm) {
      onConfirm(selectedRowKeys as number[])
      setSelectedRowKeys([])
    }
  }

  // 自动添加（自动添加模式）
  const handleAdd = async () => {
    if (!projectId) {
      message.warning('请先选择项目')
      return
    }

    if (selectedRowKeys.length === 0) {
      message.warning('请至少选择一个素材')
      return
    }

    setSubmitting(true)
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          material_ids: selectedRowKeys.map(Number)
        })
      })

      if (response.ok) {
        message.success(`成功添加 ${selectedRowKeys.length} 个素材`)
        if (onSuccess) {
          onSuccess()
        }
        setSelectedRowKeys([])
        onCancel()
      } else {
        const error = await response.json()
        message.error(error.detail || '添加素材失败')
      }
    } catch (error) {
      console.error('添加素材失败:', error)
      message.error('网络错误')
    } finally {
      setSubmitting(false)
    }
  }

  // N4: select every (still-selectable) material of one folder
  const handleSelectFolder = (folderId: number | null) => {
    const groupIds = filteredData
      .filter(item => item.folder_id === folderId)
      .filter(item => !existingMaterialIds.includes(item.id))
      .map(item => item.id)
    if (groupIds.length === 0) {
      message.warning('该文件夹无可选素材')
      return
    }
    setSelectedRowKeys(prev => {
      const current = new Set(prev as number[])
      groupIds.forEach(id => current.add(id))
      return Array.from(current)
    })
    message.success(`已选择该文件夹 ${groupIds.length} 个素材`)
  }

  // 筛选数据
  const filteredData = materials.filter(item =>
    item.name.toLowerCase().includes(searchText.toLowerCase())
  )

  // 取消
  const handleCancel = () => {
    setSelectedRowKeys([])
    onCancel()
  }

  return (
    <Modal
      title="添加素材"
      open={visible}
      onCancel={handleCancel}
      onOk={isCallbackMode ? handleConfirm : handleAdd}
      width={800}
      okText="添加"
      cancelText="取消"
      confirmLoading={isAutoAddMode ? submitting : false}
      okButtonProps={{ disabled: selectedRowKeys.length === 0 }}
    >
      <div style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索素材名称..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
        />
      </div>

      <div style={{ marginBottom: 8, color: '#666', fontSize: 12 }}>
        已选择 {selectedRowKeys.length} 个素材
      </div>

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={isCallbackMode ? materials : filteredData}
        rowKey="id"
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 条记录`
        }}
        scroll={{ y: 400 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <div>
                  <div style={{ marginBottom: 16 }}>暂无可用的素材</div>
                  <div style={{ color: '#999', fontSize: 12, marginBottom: 16 }}>
                    请先上传文档素材
                  </div>
                </div>
              }
            />
          )
        }}
      />
    </Modal>
  )
}

export default AddMaterialDialog
