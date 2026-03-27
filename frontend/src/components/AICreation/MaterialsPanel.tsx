/**
 * MaterialsPanel - 素材库面板
 * 显示当前项目的文档素材
 */
import { useState, useEffect } from 'react'
import { List, Button, Input, Empty, Spin, Tag, Checkbox } from 'antd'
import { FileTextOutlined, PlusOutlined } from '@ant-design/icons'
import AddMaterialDialog from '../common/AddMaterialDialog'

const { Search } = Input

interface Material {
  id: string | number
  type: 'document' | 'search'
  title: string
  content: string
  preview: string
  docType?: string
}

interface MaterialsPanelProps {
  projectId: number | null
  onInsert: (content: string) => void
  /** 素材选中状态变化回调 */
  onMaterialsSelect?: (materials: { id: string | number; name: string; content: string; type: string }[]) => void
  /** 当前选中的素材 ID 列表 */
  selectedMaterialIds?: (string | number)[]
}

const MaterialsPanel: React.FC<MaterialsPanelProps> = ({
  projectId,
  onInsert,
  onMaterialsSelect,
  selectedMaterialIds = []
}) => {
  const [materials, setMaterials] = useState<Material[]>([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [addDialogVisible, setAddDialogVisible] = useState(false)
  // 内部管理选中状态
  const [internalSelectedIds, setInternalSelectedIds] = useState<Set<string | number>>(new Set())

  // 获取项目素材
  const fetchMaterials = async () => {
    if (!projectId) return

    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/materials`)
      if (response.ok) {
        const data = await response.json()
        // 适配新数据结构 - 使用文档素材
        const documents = (data.documents || []).map((d: any) => ({
          id: d.id,
          type: 'document',
          title: d.name,
          content: d.content || '',
          preview: d.content?.substring(0, 100) || '',
          docType: d.type
        }))
        setMaterials(documents)
      }
    } catch (error) {
      console.error('获取素材失败:', error)
      setMaterials([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMaterials()
  }, [projectId])

  // 当选中状态变化时，通知父组件
  useEffect(() => {
    if (onMaterialsSelect) {
      const selectedMaterials = materials
        .filter(m => internalSelectedIds.has(m.id))
        .map(m => ({
          id: m.id,
          name: m.title,
          content: m.content,
          type: m.type
        }))
      onMaterialsSelect(selectedMaterials)
    }
  }, [internalSelectedIds, materials, onMaterialsSelect])

  // 切换素材选中状态
  const handleToggleSelect = (materialId: string | number) => {
    setInternalSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(materialId)) {
        newSet.delete(materialId)
      } else {
        newSet.add(materialId)
      }
      return newSet
    })
  }

  // 筛选素材
  const filteredMaterials = materials.filter(m =>
    m.title.toLowerCase().includes(searchText.toLowerCase()) ||
    m.preview.toLowerCase().includes(searchText.toLowerCase())
  )

  // 获取类型标签
  const getTypeTag = (docType?: string) => {
    const typeMap: Record<string, { color: string; text: string }> = {
      pdf: { color: 'red', text: 'PDF' },
      docx: { color: 'blue', text: 'Word' },
      txt: { color: 'default', text: 'TXT' }
    }
    if (!docType) return null
    const config = typeMap[docType] || { color: 'default', text: docType }
    return <Tag color={config.color} style={{ marginLeft: 8 }}>{config.text}</Tag>
  }

  const renderMaterialList = (materials: Material[]) => (
    <List
      size="small"
      dataSource={materials}
      renderItem={(item) => {
        const isSelected = internalSelectedIds.has(item.id)
        return (
          <List.Item
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              transition: 'background 0.2s',
              background: isSelected ? '#e6f7ff' : 'transparent',
              borderLeft: isSelected ? '3px solid #1890ff' : '3px solid transparent'
            }}
            onClick={() => handleToggleSelect(item.id)}
            onMouseEnter={(e) => {
              if (!isSelected) e.currentTarget.style.background = '#f5f5f5'
            }}
            onMouseLeave={(e) => {
              if (!isSelected) e.currentTarget.style.background = 'transparent'
            }}
          >
            <div style={{ width: '100%' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 4
              }}>
                <span style={{ fontWeight: 500, fontSize: 13, display: 'flex', alignItems: 'center' }}>
                  <Checkbox
                    checked={isSelected}
                    onClick={(e) => e.stopPropagation()}
                    style={{ marginRight: 8 }}
                  />
                  <FileTextOutlined style={{ marginRight: 8, color: isSelected ? '#1890ff' : '#666' }} />
                  <span style={{ color: isSelected ? '#1890ff' : 'inherit' }}>{item.title}</span>
                  {getTypeTag(item.docType)}
                </span>
                <Button
                  type="text"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={(e) => {
                    e.stopPropagation()
                    onInsert(item.content)
                  }}
                />
              </div>
              <div style={{
                fontSize: 12,
                color: '#666',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                marginLeft: 24
              }}>
                {item.preview}
              </div>
            </div>
          </List.Item>
        )
      }}
    />
  )

  if (!projectId) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Empty description="请先选择或创建项目" />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部操作栏 */}
      <div style={{ padding: 16, borderBottom: '1px solid #f0f0f0' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setAddDialogVisible(true)}
          disabled={!projectId}
          block
          style={{ marginBottom: 12 }}
        >
          添加素材
        </Button>
        <Search
          placeholder="搜索素材"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
        />
      </div>

      {/* 素材列表 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : filteredMaterials.length === 0 ? (
          <Empty
            description={materials.length === 0 ? "暂无素材，点击上方按钮添加" : "未找到匹配的素材"}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <div>
            <div style={{
              padding: '12px 0',
              borderBottom: '1px solid #f0f0f0',
              marginBottom: 12,
              fontWeight: 500,
              color: '#666'
            }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              文档素材 <Tag color="blue" style={{ marginLeft: 8 }}>{filteredMaterials.length}</Tag>
            </div>
            {renderMaterialList(filteredMaterials)}
          </div>
        )}
      </div>

      {/* 添加素材对话框 */}
      <AddMaterialDialog
        visible={addDialogVisible}
        projectId={projectId}
        onCancel={() => setAddDialogVisible(false)}
        onSuccess={() => {
          fetchMaterials()
        }}
      />
    </div>
  )
}

export default MaterialsPanel
