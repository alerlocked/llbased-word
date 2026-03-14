import { useState, useEffect } from 'react'
import { Tabs, Button, Input, Space, Empty, Modal, message, Checkbox, Tag } from 'antd'
import { PlusOutlined, SearchOutlined, SwapOutlined, FileTextOutlined, SearchOutlined as SearchIcon } from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'
import MaterialCard from './MaterialCard'

/**
 * 素材面板组件
 * 支持文档素材和检索结果两种类型
 * 支持批量查找替换功能
 */

interface DocumentMaterial {
  id: number
  name: string
  type: string
  content: string
  pages?: Array<{
    page_number: number
    image_path: string
    content: string
  }>
  createdAt: string
}

interface SearchResult {
  id: number
  title: string
  content: string
  source: string
  searchType: 'local' | 'web' | 'rag'
  createdAt: string
}

interface MaterialPanelProps {
  projectId?: number
  documentMaterials: DocumentMaterial[]
  searchResults: SearchResult[]
  onAddMaterial: () => void
  onRemoveMaterial: (materialId: number) => void
  onDragStart?: (material: any) => void
  onMaterialsUpdate?: (materials: DocumentMaterial[]) => void
}

const MaterialPanel: React.FC<MaterialPanelProps> = ({
  projectId,
  documentMaterials,
  searchResults,
  onAddMaterial,
  onRemoveMaterial,
  onDragStart,
  onMaterialsUpdate
}) => {
  const { colors } = useTheme()
  const [activeTab, setActiveTab] = useState('document')
  const [searchText, setSearchText] = useState('')
  const [replaceModalOpen, setReplaceModalOpen] = useState(false)
  const [findText, setFindText] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [caseSensitive, setCaseSensitive] = useState(false)
  const [wholeWord, setWholeWord] = useState(false)
  const [materials, setMaterials] = useState<DocumentMaterial[]>(documentMaterials)

  // 同步外部materials更新
  useEffect(() => {
    setMaterials(documentMaterials)
  }, [documentMaterials])

  /**
   * 批量查找替换
   */
  const handleBatchReplace = () => {
    if (!findText) {
      message.warning('请输入要查找的文本')
      return
    }

    let totalReplaced = 0
    const updatedMaterials = materials.map(material => {
      let newContent = material.content

      if (caseSensitive) {
        if (wholeWord) {
          const regex = new RegExp(`\\b${findText}\\b`, 'g')
          const matches = newContent.match(regex)
          if (matches) {
            totalReplaced += matches.length
            newContent = newContent.replace(regex, replaceText)
          }
        } else {
          const count = (newContent.match(new RegExp(findText, 'g')) || []).length
          totalReplaced += count
          newContent = newContent.split(findText).join(replaceText)
        }
      } else {
        if (wholeWord) {
          const regex = new RegExp(`\\b${findText}\\b`, 'gi')
          const matches = newContent.match(regex)
          if (matches) {
            totalReplaced += matches.length
            newContent = newContent.replace(regex, replaceText)
          }
        } else {
          const regex = new RegExp(findText, 'gi')
          const matches = newContent.match(regex)
          if (matches) {
            totalReplaced += matches.length
            newContent = newContent.replace(regex, replaceText)
          }
        }
      }

      return { ...material, content: newContent }
    })

    if (totalReplaced > 0) {
      setMaterials(updatedMaterials)
      if (onMaterialsUpdate) {
        onMaterialsUpdate(updatedMaterials)
      }
      message.success(`已替换 ${totalReplaced} 处`)
      setReplaceModalOpen(false)
      setFindText('')
      setReplaceText('')
    } else {
      message.info('未找到匹配的文本')
    }
  }

  /**
   * 统计匹配数量
   */
  const countMatches = (): number => {
    if (!findText) return 0

    let count = 0
    materials.forEach(material => {
      if (caseSensitive) {
        if (wholeWord) {
          const regex = new RegExp(`\\b${findText}\\b`, 'g')
          const matches = material.content.match(regex)
          count += matches ? matches.length : 0
        } else {
          const matches = material.content.match(new RegExp(findText, 'g'))
          count += matches ? matches.length : 0
        }
      } else {
        if (wholeWord) {
          const regex = new RegExp(`\\b${findText}\\b`, 'gi')
          const matches = material.content.match(regex)
          count += matches ? matches.length : 0
        } else {
          const regex = new RegExp(findText, 'gi')
          const matches = material.content.match(regex)
          count += matches ? matches.length : 0
        }
      }
    })

    return count
  }

  // 过滤素材
  const filteredDocuments = materials.filter(material =>
    material.name.toLowerCase().includes(searchText.toLowerCase()) ||
    material.content.toLowerCase().includes(searchText.toLowerCase())
  )

  const filteredSearchResults = searchResults.filter(result =>
    result.title.toLowerCase().includes(searchText.toLowerCase()) ||
    result.content.toLowerCase().includes(searchText.toLowerCase())
  )

  // 获取类型标签
  const getTypeTag = (type: string) => {
    const typeMap: Record<string, { color: string; text: string }> = {
      pdf: { color: 'red', text: 'PDF' },
      docx: { color: 'blue', text: 'Word' },
      txt: { color: 'default', text: 'TXT' }
    }
    const config = typeMap[type] || { color: 'default', text: type }
    return <Tag color={config.color}>{config.text}</Tag>
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: colors.bgPrimary
    }}>
      {/* 标题和操作栏 */}
      <div style={{
        padding: '16px',
        borderBottom: `1px solid ${colors.borderColor}`,
        backgroundColor: colors.bgSecondary
      }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <h3 style={{ margin: 0, color: colors.textPrimary }}>素材库</h3>
            <Space>
              {activeTab === 'document' && (
                <Button
                  icon={<SwapOutlined />}
                  onClick={() => setReplaceModalOpen(true)}
                >
                  批量替换
                </Button>
              )}
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={onAddMaterial}
              >
                添加素材
              </Button>
            </Space>
          </div>

          {/* 搜索框 */}
          <Input
            placeholder="搜索素材..."
            prefix={<SearchIcon />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
        </Space>
      </div>

      {/* 标签页 */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{ flex: 1, overflow: 'hidden' }}
        tabBarStyle={{
          margin: 0,
          padding: '0 16px',
          backgroundColor: colors.bgSecondary
        }}
        items={[
          {
            key: 'document',
            label: (
              <span>
                <FileTextOutlined style={{ marginRight: 4 }} />
                文档 ({materials.length})
              </span>
            ),
            children: (
              <div style={{
                height: 'calc(100vh - 280px)',
                overflowY: 'auto',
                padding: '16px'
              }}>
                {filteredDocuments.length > 0 ? (
                  <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    {filteredDocuments.map(material => (
                      <MaterialCard
                        key={material.id}
                        type="document"
                        data={material}
                        onRemove={() => onRemoveMaterial(material.id)}
                        onDragStart={onDragStart}
                      />
                    ))}
                  </Space>
                ) : (
                  <Empty
                    description={searchText ? '未找到匹配的素材' : '暂无素材，请点击"添加素材"'}
                    style={{ marginTop: 60 }}
                  />
                )}
              </div>
            )
          },
          {
            key: 'search',
            label: (
              <span>
                <SearchOutlined style={{ marginRight: 4 }} />
                检索结果 ({searchResults.length})
              </span>
            ),
            children: (
              <div style={{
                height: 'calc(100vh - 280px)',
                overflowY: 'auto',
                padding: '16px'
              }}>
                {filteredSearchResults.length > 0 ? (
                  <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    {filteredSearchResults.map(result => (
                      <MaterialCard
                        key={result.id}
                        type="search"
                        data={result}
                        onRemove={() => onRemoveMaterial(result.id)}
                        onDragStart={onDragStart}
                      />
                    ))}
                  </Space>
                ) : (
                  <Empty
                    description={searchText ? '未找到匹配的结果' : '暂无检索结果'}
                    style={{ marginTop: 60 }}
                  />
                )}
              </div>
            )
          }
        ]}
      />

      {/* 批量替换对话框 */}
      <Modal
        title="批量查找替换"
        open={replaceModalOpen}
        onCancel={() => {
          setReplaceModalOpen(false)
          setFindText('')
          setReplaceText('')
        }}
        onOk={handleBatchReplace}
        okText="全部替换"
        cancelText="取消"
        width={500}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <div style={{ marginBottom: 8, color: colors.textPrimary }}>查找内容：</div>
            <Input
              placeholder="输入要查找的文本"
              value={findText}
              onChange={(e) => setFindText(e.target.value)}
              size="large"
            />
          </div>

          <div>
            <div style={{ marginBottom: 8, color: colors.textPrimary }}>替换为：</div>
            <Input
              placeholder="输入替换后的文本"
              value={replaceText}
              onChange={(e) => setReplaceText(e.target.value)}
              size="large"
            />
          </div>

          <Space direction="vertical">
            <Checkbox
              checked={caseSensitive}
              onChange={(e) => setCaseSensitive(e.target.checked)}
            >
              区分大小写
            </Checkbox>
            <Checkbox
              checked={wholeWord}
              onChange={(e) => setWholeWord(e.target.checked)}
            >
              全词匹配
            </Checkbox>
          </Space>

          {findText && (
            <div style={{
              padding: 12,
              backgroundColor: colors.bgSecondary,
              borderRadius: 4,
              color: colors.textSecondary
            }}>
              找到 <strong style={{ color: colors.primary }}>{countMatches()}</strong> 处匹配
            </div>
          )}
        </Space>
      </Modal>
    </div>
  )
}

export default MaterialPanel
