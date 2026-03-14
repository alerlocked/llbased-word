import { useState } from 'react'
import { Card, Button, Typography, Tag, Input, Space, Popconfirm, message, Image, Divider, Switch, Tooltip } from 'antd'
import {
  UpOutlined,
  DownOutlined,
  DeleteOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  FileTextOutlined,
  PictureOutlined,
  CopyOutlined,
  SearchOutlined
} from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'

const { Text, Paragraph } = Typography
const { TextArea } = Input

/**
 * 通用素材卡片组件
 * 支持文档素材和检索结果两种类型
 * 文档资料支持图文对照查看
 */

interface SearchResult {
  id: number
  title: string
  content: string
  source: string
  searchType: 'local' | 'web' | 'rag'
  createdAt: string
}

interface DocumentPage {
  page_number: number
  image_path: string
  content: string
  figures?: Array<{
    type: string
    caption: string
    description?: string
  }>
}

interface DocumentMaterial {
  id: number
  name: string
  type: string
  content: string
  pages: DocumentPage[]
  createdAt: string
}

interface MaterialCardProps {
  type: 'document' | 'search'
  data: DocumentMaterial | SearchResult
  onRemove?: () => void
  onDragStart?: (data: any) => void
}

const MaterialCard: React.FC<MaterialCardProps> = ({
  type,
  data,
  onRemove,
  onDragStart
}) => {
  const { colors } = useTheme()
  const [expanded, setExpanded] = useState(false)
  const [showOcrText, setShowOcrText] = useState(false)

  /**
   * 处理拖拽开始
   */
  const handleDragStart = (e: React.DragEvent) => {
    if (onDragStart) {
      onDragStart(data)
    }
    // 设置拖拽数据
    e.dataTransfer.effectAllowed = 'copy'
    e.dataTransfer.setData('application/json', JSON.stringify({ type, data }))
  }

  /**
   * 复制文本到剪贴板
   */
  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text)
    message.success('文本已复制')
  }

  // 渲染检索结果
  const renderSearchContent = (result: SearchResult) => {
    const typeColors = {
      local: 'green',
      web: 'blue',
      rag: 'purple'
    }
    const typeLabels = {
      local: '本地',
      web: '网络',
      rag: 'RAG'
    }

    return (
      <div>
        <div style={{ marginBottom: 12 }}>
          <Tag color={typeColors[result.searchType]}>
            {typeLabels[result.searchType]}
          </Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            来源: {result.source}
          </Text>
        </div>
        {expanded && (
          <div
            style={{
              maxHeight: 400,
              overflowY: 'auto',
              padding: 12,
              backgroundColor: colors.bgPrimary,
              borderRadius: 4,
              color: colors.textPrimary,
              lineHeight: 1.8,
              whiteSpace: 'pre-wrap'
            }}
          >
            {result.content}
          </div>
        )}
      </div>
    )
  }

  // 渲染文档素材 (所见即所得模式)
  const renderDocumentContent = (material: DocumentMaterial) => {
    // 处理图片路径，添加后端地址前缀
    const getImageUrl = (path: string) => {
      const cleanPath = path.replace(/^backend[\\/]/, '').replace(/\\/g, '/')
      return `http://localhost:8000/static/${cleanPath}`
    }

    return (
      <div>
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Tag icon={<FileTextOutlined />} color="orange">
              {material.pages?.length || 0} 页
            </Tag>
            <Tag>{material.type?.toUpperCase()}</Tag>
          </Space>
          <Space>
            <span style={{ fontSize: 12, color: colors.textSecondary }}>显示识别文本</span>
            <Switch
              size="small"
              checked={showOcrText}
              onChange={setShowOcrText}
              checkedChildren={<FileTextOutlined />}
              unCheckedChildren={<PictureOutlined />}
            />
          </Space>
        </div>

        {expanded && (
          <div style={{
            maxHeight: 600,
            overflowY: 'auto',
            padding: '0 4px',
            backgroundColor: colors.bgPrimary,
            borderRadius: 4
          }}>
            {material.pages?.map((page, index) => (
              <div key={index} style={{ marginBottom: 24, position: 'relative' }}>
                {/* 页码标记 */}
                <div style={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  zIndex: 1,
                  backgroundColor: 'rgba(0,0,0,0.5)',
                  color: 'white',
                  padding: '2px 8px',
                  borderRadius: 12,
                  fontSize: 12
                }}>
                  第 {page.page_number} 页
                </div>

                {/* 页面图片 */}
                <div style={{
                  border: `1px solid ${colors.borderColor}`,
                  borderRadius: 4,
                  overflow: 'hidden',
                  marginBottom: 8
                }}>
                  <Image
                    src={getImageUrl(page.image_path)}
                    alt={`第 ${page.page_number} 页`}
                    width="100%"
                    style={{ display: 'block' }}
                    fallback="https://via.placeholder.com/400x600?text=Image+Not+Found"
                  />
                </div>

                {/* OCR 文本对照区域 */}
                {showOcrText && (
                  <div style={{
                    padding: 12,
                    backgroundColor: colors.bgSecondary,
                    borderRadius: 4,
                    border: `1px dashed ${colors.borderColor}`,
                    marginTop: 8
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>OCR 识别结果</Text>
                      <Tooltip title="复制文本">
                        <Button
                          type="text"
                          size="small"
                          icon={<CopyOutlined />}
                          onClick={() => handleCopyText(page.content)}
                        />
                      </Tooltip>
                    </div>

                    {/* 提取的图表信息展示 */}
                    {page.figures && page.figures.length > 0 && (
                      <div style={{ marginBottom: 16 }}>
                        <Text strong style={{ fontSize: 13 }}>提取的图表/插图:</Text>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                          {page.figures.map((fig, fIdx) => (
                            <div key={fIdx} style={{
                              border: `1px solid ${colors.borderColor}`,
                              padding: 8,
                              borderRadius: 4,
                              width: '100%',
                              backgroundColor: colors.bgPrimary
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Tag color="blue">{fig.type}</Tag>
                                <Text strong>{fig.caption}</Text>
                              </div>
                              {fig.description && (
                                <Paragraph
                                  style={{ marginTop: 4, fontSize: 12, color: colors.textSecondary }}
                                  ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                                >
                                  {fig.description}
                                </Paragraph>
                              )}
                            </div>
                          ))}
                        </div>
                        <Divider style={{ margin: '12px 0' }} />
                      </div>
                    )}

                    <Paragraph
                      ellipsis={{ rows: 5, expandable: true, symbol: '展开全部' }}
                      style={{
                        fontSize: 13,
                        color: colors.textPrimary,
                        whiteSpace: 'pre-wrap',
                        lineHeight: 1.6
                      }}
                    >
                      {page.content}
                    </Paragraph>
                  </div>
                )}

                {index < material.pages.length - 1 && <Divider style={{ margin: '24px 0' }} />}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  let title = ''
  if (type === 'search') title = (data as SearchResult).title
  else if (type === 'document') title = (data as DocumentMaterial).name

  return (
    <Card
      draggable
      onDragStart={handleDragStart}
      style={{
        backgroundColor: colors.bgSecondary,
        borderColor: colors.borderColor,
        cursor: 'move'
      }}
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text strong style={{ color: colors.textPrimary, maxWidth: 200 }} ellipsis={{ tooltip: title }}>
            {title}
          </Text>
          <div>
            <Button
              type="text"
              size="small"
              icon={expanded ? <UpOutlined /> : <DownOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                setExpanded(!expanded)
              }}
            />
            {onRemove && (
              <Popconfirm
                title="确定删除此素材？"
                description="删除后无法恢复"
                onConfirm={(e) => {
                  e?.stopPropagation()
                  onRemove()
                }}
                okText="确定"
                cancelText="取消"
              >
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                />
              </Popconfirm>
            )}
          </div>
        </div>
      }
    >
      {type === 'search' && renderSearchContent(data as SearchResult)}
      {type === 'document' && renderDocumentContent(data as DocumentMaterial)}
    </Card>
  )
}

export default MaterialCard
