/**
 * MaterialDrawer - 素材库抽屉
 * 支持文件夹管理和知识库范围选择
 */
import { useState, useEffect } from 'react'
import { Drawer, Upload, Button, message, Tabs, Divider } from 'antd'
import {
  CloudUploadOutlined,
  DatabaseOutlined,
  FolderOutlined
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { colors } from '../../styles/design-tokens'
import FolderTree, { FolderNode } from '../MaterialLibrary/FolderTree'
import FileList, { MaterialFile } from '../MaterialLibrary/FileList'
import KnowledgeScopeSelector from '../MaterialLibrary/KnowledgeScopeSelector'

const FOLDERS_STORAGE_KEY = 'material_folders'
const SCOPE_STORAGE_KEY = 'knowledge_scope_selection'

interface MaterialDrawerProps {
  visible: boolean
  onClose: () => void
  projectId: number | null
  onInsert: (content: string) => void
}

// 默认文件夹结构
const defaultFolders: FolderNode[] = [
  {
    key: 'folder_process',
    title: '工艺规程',
    children: [
      { key: 'folder_model_a', title: '型号 A' },
      { key: 'folder_model_b', title: '型号 B' }
    ]
  },
  {
    key: 'folder_standard',
    title: '检验标准'
  },
  {
    key: 'folder_training',
    title: '培训资料'
  }
]

const MaterialDrawer: React.FC<MaterialDrawerProps> = ({
  visible,
  onClose,
  projectId,
  onInsert
}) => {
  const [materials, setMaterials] = useState<MaterialFile[]>([])
  const [loading, setLoading] = useState(false)
  const [folders, setFolders] = useState<FolderNode[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string>('root')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState('files')

  // 加载文件夹和素材
  useEffect(() => {
    if (visible) {
      loadFolders()
      if (projectId) {
        fetchMaterials()
      }
      loadSelectedScopes()
    }
  }, [visible, projectId])

  // 从 localStorage 加载文件夹
  const loadFolders = () => {
    const saved = localStorage.getItem(FOLDERS_STORAGE_KEY)
    if (saved) {
      try {
        setFolders(JSON.parse(saved))
      } catch {
        setFolders(defaultFolders)
      }
    } else {
      setFolders(defaultFolders)
    }
  }

  // 保存文件夹到 localStorage
  const saveFolders = (newFolders: FolderNode[]) => {
    localStorage.setItem(FOLDERS_STORAGE_KEY, JSON.stringify(newFolders))
    setFolders(newFolders)
  }

  // 加载知识库范围选择
  const loadSelectedScopes = () => {
    const saved = localStorage.getItem(SCOPE_STORAGE_KEY)
    if (saved) {
      try {
        setSelectedScopes(JSON.parse(saved))
      } catch {
        // 使用默认值
      }
    }
  }

  // 获取素材列表
  const fetchMaterials = async () => {
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/materials`)
      if (response.ok) {
        const data = await response.json()
        // 转换数据格式
        const files: MaterialFile[] = []
        if (data.documents) {
          data.documents.forEach((doc: any) => {
            files.push({
              id: doc.id,
              name: doc.name,
              url: '',
              type: doc.type || 'document',
              created_at: doc.createdAt || new Date().toISOString()
            })
          })
        }
        setMaterials(files)
      }
    } catch (error) {
      console.error('获取素材失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 文件夹更新处理
  const handleFoldersUpdate = (newFolders: FolderNode[]) => {
    saveFolders(newFolders)
  }

  // 文件选择处理
  const handleFileSelect = (file: MaterialFile) => {
    if (file.type.startsWith('image/') && file.url) {
      onInsert(`![${file.name}](${file.url})`)
    } else {
      onInsert(file.name)
    }
    onClose()
  }

  // 文件删除处理
  const handleFileDelete = async (fileId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/creation/projects/${projectId}/materials/${fileId}`,
        { method: 'DELETE' }
      )
      if (response.ok) {
        message.success('删除成功')
        fetchMaterials()
      }
    } catch (error) {
      message.error('删除失败')
    }
  }

  // 文件移动处理
  const handleFileMove = (fileId: number, folderId: string) => {
    setMaterials(prev =>
      prev.map(m => m.id === fileId ? { ...m, folderId } : m)
    )
    message.success('文件已移动')
  }

  // 上传配置
  const uploadProps: UploadProps = {
    name: 'file',
    action: `http://localhost:8000/api/creation/projects/${projectId}/documents`,
    showUploadList: false,
    onChange(info) {
      if (info.file.status === 'done') {
        message.success(`${info.file.name} 上传成功`)
        fetchMaterials()
      } else if (info.file.status === 'error') {
        message.error(`${info.file.name} 上传失败`)
      }
    }
  }

  // 获取扁平化的文件夹列表（用于选择器）
  const getFlatFolders = () => {
    const result: { key: string; title: string }[] = []
    const traverse = (nodes: FolderNode[], prefix = '') => {
      nodes.forEach(node => {
        result.push({ key: node.key, title: prefix + node.title })
        if (node.children) {
          traverse(node.children, prefix + '  ')
        }
      })
    }
    traverse(folders)
    return result
  }

  // 获取知识库范围的文件夹数据
  const getScopeFolders = () => {
    return folders.map(f => ({
      key: f.key,
      title: f.title,
      count: materials.filter(m => m.folderId === f.key).length,
      children: f.children?.map(c => ({
        key: c.key,
        title: c.title,
        count: materials.filter(m => m.folderId === c.key).length
      }))
    }))
  }

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <DatabaseOutlined style={{ color: colors.primary }} />
          <span>素材库</span>
        </div>
      }
      placement="right"
      width={520}
      onClose={onClose}
      open={visible}
      styles={{
        body: { padding: 0 }
      }}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{ padding: '0 16px' }}
        items={[
          {
            key: 'files',
            label: (
              <span>
                <FolderOutlined />
                文件管理
              </span>
            ),
            children: (
              <div style={{ display: 'flex', height: 'calc(100vh - 150px)' }}>
                {/* 左侧：文件夹树 */}
                <div style={{
                  width: 180,
                  borderRight: `1px solid ${colors.borderLight}`,
                  overflow: 'auto'
                }}>
                  <FolderTree
                    folders={folders}
                    selectedFolder={selectedFolder}
                    onSelect={setSelectedFolder}
                    onUpdate={handleFoldersUpdate}
                  />
                </div>

                {/* 右侧：文件列表 */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  {/* 工具栏 */}
                  <div style={{
                    padding: '8px 16px',
                    borderBottom: `1px solid ${colors.borderLight}`,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <span style={{ color: colors.textSecondary, fontSize: 13 }}>
                      {selectedFolder === 'root' ? '全部文件' :
                        folders.find(f => f.key === selectedFolder)?.title || '文件'}
                    </span>
                    <Upload {...uploadProps}>
                      <Button
                        type="primary"
                        icon={<CloudUploadOutlined />}
                        size="small"
                      >
                        上传
                      </Button>
                    </Upload>
                  </div>

                  {/* 文件列表 */}
                  <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
                    <FileList
                      files={materials}
                      loading={loading}
                      currentFolder={selectedFolder}
                      onSelect={handleFileSelect}
                      onDelete={handleFileDelete}
                      onMove={handleFileMove}
                      folders={getFlatFolders()}
                    />
                  </div>
                </div>
              </div>
            )
          },
          {
            key: 'scope',
            label: (
              <span>
                <DatabaseOutlined />
                知识库范围
              </span>
            ),
            children: (
              <div style={{ padding: 16 }}>
                <p style={{
                  color: colors.textSecondary,
                  marginBottom: 16,
                  fontSize: 13
                }}>
                  选择 AI 检索时使用的知识库范围。只有选中的文件夹中的内容会被用于检索。
                </p>
                <KnowledgeScopeSelector
                  folders={getScopeFolders()}
                  selectedScopes={selectedScopes}
                  onChange={(scopes) => {
                    setSelectedScopes(scopes)
                    localStorage.setItem(SCOPE_STORAGE_KEY, JSON.stringify(scopes))
                  }}
                />
                <Divider />
                <div style={{
                  padding: 12,
                  background: colors.bgTertiary,
                  borderRadius: 8,
                  fontSize: 12,
                  color: colors.textSecondary
                }}>
                  <strong style={{ color: colors.textPrimary }}>使用提示：</strong>
                  <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
                    <li>选择需要检索的文件夹</li>
                    <li>AI 对话时只会从选中的知识库中检索</li>
                    <li>选择越精确，检索结果越准确</li>
                  </ul>
                </div>
              </div>
            )
          }
        ]}
      />
    </Drawer>
  )
}

export default MaterialDrawer
