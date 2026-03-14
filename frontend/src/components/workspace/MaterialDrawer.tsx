/**
 * MaterialDrawer - 素材库抽屉
 */
import { useState, useEffect } from 'react'
import { Drawer, List, Image, Empty, Spin, message } from 'antd'
import { colors } from '../../styles/design-tokens'

interface Material {
  id: number
  name: string
  url: string
  type: string
  created_at: string
}

interface MaterialDrawerProps {
  visible: boolean
  onClose: () => void
  projectId: number | null
  onInsert: (content: string) => void
}

const MaterialDrawer: React.FC<MaterialDrawerProps> = ({
  visible,
  onClose,
  projectId,
  onInsert
}) => {
  const [materials, setMaterials] = useState<Material[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (visible && projectId) {
      fetchMaterials()
    }
  }, [visible, projectId])

  const fetchMaterials = async () => {
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/materials`)
      if (response.ok) {
        const data = await response.json()
        setMaterials(data.items || [])
      }
    } catch (error) {
      message.error('获取素材失败')
    } finally {
      setLoading(false)
    }
  }

  const handleInsert = (material: Material) => {
    if (material.type.startsWith('image/')) {
      onInsert(`![${material.name}](${material.url})`)
    } else {
      onInsert(material.name)
    }
    onClose()
  }

  return (
    <Drawer
      title="素材库"
      placement="right"
      width={400}
      onClose={onClose}
      open={visible}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : materials.length === 0 ? (
        <Empty description="暂无素材" />
      ) : (
        <List
          dataSource={materials}
          renderItem={(item) => (
            <List.Item
              onClick={() => handleInsert(item)}
              style={{ cursor: 'pointer' }}
            >
              <List.Item.Meta
                avatar={
                  item.type.startsWith('image/') ? (
                    <Image src={item.url} width={48} height={48} style={{ objectFit: 'cover' }} />
                  ) : (
                    <div style={{ width: 48, height: 48, background: colors.bgTertiary, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      📄
                    </div>
                  )
                }
                title={item.name}
                description={item.type}
              />
            </List.Item>
          )}
        />
      )}
    </Drawer>
  )
}

export default MaterialDrawer
