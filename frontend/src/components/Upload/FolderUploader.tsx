import { useState, useRef } from 'react'
import { Button, Card, Checkbox, Space, message, Typography } from 'antd'
import { FolderOpenOutlined, CheckSquareOutlined, BorderOutlined } from '@ant-design/icons'
import { useTheme } from '../../contexts/ThemeContext'

const { Text } = Typography

/**
 * 文件夹上传组件
 * 支持选择文件夹,显示文件列表供用户勾选,并提供全选功能
 */

interface FileItem {
  file: File
  selected: boolean
  id: string
  /** 相对路径（保留文件夹结构） */
  relativePath: string
  /** 目录深度 */
  depth: number
}

interface FolderUploaderProps {
  onFilesSelected: (files: File[]) => void
  accept?: string
}

const FolderUploader: React.FC<FolderUploaderProps> = ({ onFilesSelected, accept = '.pdf,.docx,.doc,.txt' }) => {
  const { colors } = useTheme()
  const [fileList, setFileList] = useState<FileItem[]>([])
  const [allSelected, setAllSelected] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  /**
   * 格式化文件大小
   */
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / 1024 / 1024).toFixed(2) + ' MB'
  }

  /**
   * 检查文件是否为支持的格式
   */
  const isValidFile = (fileName: string): boolean => {
    const ext = fileName.toLowerCase().substring(fileName.lastIndexOf('.'))
    return accept.split(',').some(format => ext === format.trim())
  }

  /**
   * 处理文件夹选择
   */
  const handleFolderSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    // 过滤支持的文件，保留相对路径
    const validFiles: FileItem[] = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      // 获取 webkitRelativePath（保留文件夹层级）
      const relativePath = (file as any).webkitRelativePath || file.name
      const depth = relativePath.split('/').length - 1

      if (isValidFile(file.name)) {
        validFiles.push({
          file,
          selected: true,
          id: relativePath,  // 使用相对路径作为唯一ID
          relativePath,
          depth
        })
      }
    }

    if (validFiles.length === 0) {
      message.warning('所选文件夹中没有找到支持的文档文件')
      return
    }

    setFileList(validFiles)
    setAllSelected(true)
    message.success(`已加载 ${validFiles.length} 个文档文件`)
  }

  /**
   * 触发文件夹选择
   */
  const handleSelectFolder = () => {
    inputRef.current?.click()
  }

  /**
   * 切换单个文件选择状态
   */
  const handleToggleFile = (id: string) => {
    const updated = fileList.map(item =>
      item.id === id ? { ...item, selected: !item.selected } : item
    )
    setFileList(updated)
    setAllSelected(updated.every(item => item.selected))
  }

  /**
   * 全选/取消全选
   */
  const handleToggleAll = () => {
    const newState = !allSelected
    setAllSelected(newState)
    setFileList(fileList.map(item => ({ ...item, selected: newState })))
  }

  /**
   * 获取已选中的文件
   */
  const getSelectedFiles = (): File[] => {
    return fileList.filter(item => item.selected).map(item => item.file)
  }

  /**
   * 清空文件列表
   */
  const handleClear = () => {
    setFileList([])
    setAllSelected(false)
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  return (
    <div>
      {/* 隐藏的文件输入 */}
      <input
        ref={inputRef}
        type="file"
        webkitdirectory=""
        directory=""
        multiple
        accept={accept}
        onChange={handleFolderSelect}
        style={{ display: 'none' }}
      />

      {/* 选择文件夹按钮 */}
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<FolderOpenOutlined />}
          onClick={handleSelectFolder}
        >
          选择文件夹
        </Button>
        {fileList.length > 0 && (
          <>
            <Button
              icon={allSelected ? <BorderOutlined /> : <CheckSquareOutlined />}
              onClick={handleToggleAll}
            >
              {allSelected ? '取消全选' : '全选'}
            </Button>
            <Button onClick={handleClear}>清空</Button>
            <Text type="secondary">
              已选择 {fileList.filter(f => f.selected).length} / {fileList.length} 个文件
            </Text>
          </>
        )}
      </Space>

      {/* 文件列表 */}
      {fileList.length > 0 && (
        <Card
          title="文件列表"
          style={{
            backgroundColor: colors.bgSecondary,
            borderColor: colors.borderColor,
            maxHeight: '400px',
            overflow: 'auto'
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {fileList.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '8px 12px',
                  backgroundColor: item.selected ? colors.bgTertiary : 'transparent',
                  border: `1px solid ${colors.borderColor}`,
                  borderRadius: 4,
                  cursor: 'pointer',
                  transition: 'background-color 0.2s'
                }}
                onClick={() => handleToggleFile(item.id)}
              >
                <Checkbox
                  checked={item.selected}
                  onChange={() => handleToggleFile(item.id)}
                  onClick={(e) => e.stopPropagation()}
                />
                <div style={{ flex: 1, marginLeft: 12 }}>
                  <div style={{ color: colors.textPrimary, fontWeight: 500 }}>
                    {/* 显示完整相对路径 */}
                    {item.relativePath}
                  </div>
                  <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 4 }}>
                    {/* 显示文件大小和目录深度 */}
                    {formatFileSize(item.file.size)} {item.depth > 0 ? `· ${item.depth} 级目录` : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

export default FolderUploader
