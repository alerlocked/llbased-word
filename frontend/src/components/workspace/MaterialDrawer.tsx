/**
 * MaterialDrawer - 素材库抽屉
 * Integrated upload, file management, and knowledge scope
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { Drawer, Upload, Button, message, Tabs, Divider, Modal, Spin, Tag, Progress, Alert } from 'antd'
import {
  CloudUploadOutlined,
  DatabaseOutlined,
  FolderOutlined,
  FileTextOutlined,
  UserOutlined,
  InboxOutlined,
  LoadingOutlined
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { colors } from '../../styles/design-tokens'
import FolderTree, { FolderNode } from '../MaterialLibrary/FolderTree'
import FileList, { MaterialFile } from '../MaterialLibrary/FileList'
import KnowledgeScopeSelector from '../MaterialLibrary/KnowledgeScopeSelector'

const { Dragger } = Upload

const API_BASE = 'http://localhost:8000/api/creation'
const SCOPE_STORAGE_KEY = 'knowledge_scope_selection'
const POLL_INTERVAL = 2000

interface MaterialDrawerProps {
  visible: boolean
  onClose: () => void
  projectId: number | null
  onInsert: (content: string) => void
  /** Open to upload tab on mount */
  defaultTab?: string
}

// Convert flat API folder tree to FolderNode[] for FolderTree component
interface ApiFolderNode {
  id: number
  name: string
  parentId: number | null
  sortOrder: number
  children: ApiFolderNode[]
}

const apiFolderToFolderNode = (nodes: ApiFolderNode[]): FolderNode[] => {
  return nodes.map(node => ({
    key: String(node.id),
    title: node.name,
    children: node.children ? apiFolderToFolderNode(node.children) : undefined,
  }))
}

const MaterialDrawer: React.FC<MaterialDrawerProps> = ({
  visible,
  onClose,
  projectId,
  onInsert,
  defaultTab
}) => {
  const [materials, setMaterials] = useState<MaterialFile[]>([])
  const [loading, setLoading] = useState(false)
  const [folders, setFolders] = useState<FolderNode[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string>('root')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState(defaultTab || 'files')

  // preview state
  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewFile, setPreviewFile] = useState<MaterialFile | null>(null)
  const [previewContent, setPreviewContent] = useState<string>('')
  const [previewLoading, setPreviewLoading] = useState(false)

  // profile learning state
  const [learningFileId, setLearningFileId] = useState<number | null>(null)

  // upload state
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [processingProgress, setProcessingProgress] = useState(0)
  const [remainingTime, setRemainingTime] = useState<number | null>(null)
  const [currentFile, setCurrentFile] = useState<string>('')
  const [pollingMaterialId, setPollingMaterialId] = useState<number | null>(null)

  const processingStartTimeRef = useRef<number | null>(null)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Sync defaultTab
  useEffect(() => {
    if (defaultTab) {
      setActiveTab(defaultTab)
    }
  }, [defaultTab])

  // load folders and materials
  useEffect(() => {
    if (visible) {
      loadFolders()
      fetchMaterials()
      loadSelectedScopes()
    }
  }, [visible])

  // auto-refresh when materials are being processed
  useEffect(() => {
    if (!visible) return
    const hasProcessing = materials.some(m =>
      m.parse_status === 'pending' || m.parse_status === 'queued' || m.parse_status === 'processing'
    )
    if (!hasProcessing) return
    const timer = setInterval(fetchMaterials, 3000)
    return () => clearInterval(timer)
  }, [visible, materials])

  // --- Polling logic ---

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const pollParseStatus = useCallback(async (materialId: number) => {
    try {
      const resp = await fetch(`http://localhost:8000/api/creation/materials/${materialId}/parse-status`)
      if (!resp.ok) return
      const data = await resp.json()

      setProcessingProgress(data.progress || 0)

      if (processingStartTimeRef.current && (data.progress || 0) > 5) {
        const elapsed = (Date.now() - processingStartTimeRef.current) / 1000
        const ratio = (data.progress || 0) / 100
        const totalEstimated = elapsed / ratio
        setRemainingTime(Math.max(0, totalEstimated - elapsed))
      }

      if (data.status === 'completed') {
        stopPolling()
        setProcessingProgress(100)
        setRemainingTime(0)
        setTimeout(() => {
          setProcessing(false)
          message.destroy('processing')
          message.success(`${currentFile} 解析完成`)
          fetchMaterials()
        }, 300)
      } else if (data.status === 'failed') {
        stopPolling()
        setProcessing(false)
        message.destroy('processing')
        message.error(`${currentFile} 解析失败: ${data.error_message || '未知错误'}`)
        fetchMaterials()
      }
    } catch {
      // Network error, keep polling
    }
  }, [currentFile, stopPolling])

  const startPolling = useCallback((materialId: number) => {
    stopPolling()
    pollTimerRef.current = setInterval(() => {
      pollParseStatus(materialId)
    }, POLL_INTERVAL)
  }, [pollParseStatus, stopPolling])

  useEffect(() => {
    if (pollingMaterialId !== null && processing) {
      startPolling(pollingMaterialId)
      pollParseStatus(pollingMaterialId)
    }
    return () => stopPolling()
  }, [pollingMaterialId])

  useEffect(() => {
    return () => { stopPolling() }
  }, [stopPolling])

  // reset upload state on close
  useEffect(() => {
    if (!visible) {
      setUploadProgress(0)
      setProcessingProgress(0)
      setRemainingTime(null)
      setPollingMaterialId(null)
      stopPolling()
    }
  }, [visible, stopPolling])

  // --- Folders (API-backed) ---

  const loadFolders = async () => {
    try {
      const resp = await fetch(`${API_BASE}/material-folders`)
      if (resp.ok) {
        const data: ApiFolderNode[] = await resp.json()
        setFolders(apiFolderToFolderNode(data))
      }
    } catch {
      console.error('获取文件夹失败')
    }
  }

  const handleCreateFolder = async (name: string, parentId: number | null = null) => {
    const resp = await fetch(`${API_BASE}/material-folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, parent_id: parentId }),
    })
    if (!resp.ok) throw new Error('创建失败')
    await loadFolders()
  }

  const handleRenameFolder = async (folderId: number, name: string) => {
    const resp = await fetch(`${API_BASE}/material-folders/${folderId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!resp.ok) throw new Error('重命名失败')
    await loadFolders()
  }

  const handleDeleteFolder = async (folderId: number) => {
    const resp = await fetch(`${API_BASE}/material-folders/${folderId}`, {
      method: 'DELETE',
    })
    if (!resp.ok) throw new Error('删除失败')
    await loadFolders()
    await fetchMaterials()
  }

  // --- Knowledge scope ---

  const loadSelectedScopes = () => {
    const saved = localStorage.getItem(SCOPE_STORAGE_KEY)
    if (saved) {
      try {
        setSelectedScopes(JSON.parse(saved))
      } catch {
        // use default
      }
    }
  }

  // --- Materials ---

  const fetchMaterials = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/projects/0/materials`)
      if (response.ok) {
        const data = await response.json()
        const files: MaterialFile[] = []
        if (data.documents) {
          data.documents.forEach((doc: Record<string, unknown>) => {
            files.push({
              id: doc.id as number,
              name: doc.name as string,
              url: '',
              type: (doc.type as string) || 'document',
              created_at: (doc.createdAt as string) || new Date().toISOString(),
              content: (doc.content as string) || '',
              parse_status: (doc.parse_status as MaterialFile['parse_status']) || 'unknown',
              parse_progress: (doc.parse_progress as number) || 0,
              parse_error: doc.parse_error as string | undefined,
              folderId: doc.folderId != null ? String(doc.folderId) : undefined,
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

  // --- Upload ---

  const handleUploadFile = (materialId: number, fileName: string) => {
    setUploading(false)
    setProcessing(true)
    setProcessingProgress(0)
    setRemainingTime(null)
    processingStartTimeRef.current = Date.now()
    setCurrentFile(fileName)
    message.loading({ content: '正在解析文档，请稍候...', key: 'processing', duration: 0 })

    if (materialId) {
      setPollingMaterialId(materialId)
    } else {
      setProcessingProgress(10)
    }
  }

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    action: `${API_BASE}/projects/${projectId || 0}/documents`,
    showUploadList: false,
    onChange(info) {
      if (info.file.status === 'uploading') {
        setUploading(true)
        setUploadProgress(info.file.percent || 0)
        setCurrentFile(info.file.name)
      }

      if (info.file.status === 'done') {
        const materialId = info.file.response?.material_id
        handleUploadFile(materialId, info.file.name)
      }

      if (info.file.status === 'error') {
        setUploading(false)
        message.error(`${info.file.name} 上传失败`)
      }
    }
  }

  // --- File operations ---

  const handleFilePreview = async (file: MaterialFile) => {
    setPreviewFile(file)
    setPreviewVisible(true)
    setPreviewLoading(true)
    setPreviewContent('')

    try {
      const response = await fetch(
        `${API_BASE}/materials/${file.id}`
      )
      if (response.ok) {
        const data = await response.json()
        setPreviewContent(data.content || data.text || '无内容预览')
      } else {
        setPreviewContent(file.content || '无法获取文件内容')
      }
    } catch (error) {
      console.error('获取预览内容失败:', error)
      setPreviewContent(file.content || '获取预览内容失败')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleFileInsert = (file: MaterialFile) => {
    if (file.type.startsWith('image/') && file.url) {
      onInsert(`![${file.name}](${file.url})`)
    } else {
      onInsert(`【引用：${file.name}】\n${file.content || ''}`)
    }
    message.success(`已添加引用: ${file.name}`)
    onClose()
  }

  const handleFileDelete = async (fileId: number) => {
    try {
      const response = await fetch(
        `${API_BASE}/materials/${fileId}`,
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

  const handleFileMove = async (fileId: number, folderId: string) => {
    try {
      const response = await fetch(`${API_BASE}/materials/${fileId}/move`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_id: folderId === 'root' ? null : Number(folderId) }),
      })
      if (response.ok) {
        message.success('文件已移动')
        fetchMaterials()
      } else {
        message.error('移动失败')
      }
    } catch {
      message.error('移动失败')
    }
  }

  const handleLearnProfile = async (file: MaterialFile) => {
    setLearningFileId(file.id)
    try {
      let content = file.content || ''
      if (!content) {
        const resp = await fetch(
          `${API_BASE}/materials/${file.id}`
        )
        if (resp.ok) {
          const data = await resp.json()
          content = data.content || data.text || ''
        }
      }

      if (!content || content.length < 10) {
        message.warning('文件内容不足，无法提取画像')
        return
      }

      const textContent = content.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()

      const resp = await fetch('http://localhost:8000/api/profile/default/learn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: textContent,
          domain: 'assembly',
          document_id: String(file.id),
        }),
      })

      if (resp.ok) {
        const data = await resp.json()
        const termsCount = data.extracted_features?.terms_count || 0
        const triplesCount = data.profile?.triples?.length || 0
        message.success(
          `画像学习完成：提取 ${triplesCount} 条知识、${termsCount} 个术语`
        )
      } else {
        message.error('画像学习失败')
      }
    } catch (error) {
      console.error('Profile learning failed:', error)
      message.error('画像学习出错')
    } finally {
      setLearningFileId(null)
    }
  }

  // helpers
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

  const formatRemainingTime = (seconds: number): string => {
    if (seconds <= 0) return '即将完成'
    if (seconds < 60) return `${Math.ceil(seconds)}秒`
    const minutes = Math.floor(seconds / 60)
    const secs = Math.ceil(seconds % 60)
    if (minutes < 60) {
      return secs > 0 ? `${minutes}分${secs}秒` : `${minutes}分钟`
    }
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return mins > 0 ? `${hours}小时${mins}分` : `${hours}小时`
  }

  // Upload tab content
  const uploadTabContent = (
    <div style={{ padding: 16 }}>
      <Dragger {...uploadProps} disabled={uploading || processing}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ color: colors.primary, fontSize: 48 }} />
        </p>
        <p className="ant-upload-text" style={{ fontSize: 16, fontWeight: 500 }}>
          点击或拖拽文件到此区域上传
        </p>
        <p className="ant-upload-hint">支持 PDF、Word、TXT 等格式，可多选上传</p>
      </Dragger>

      {/* upload progress */}
      {uploading && (
        <div style={{ marginTop: 24 }}>
          <Alert
            message="正在上传文件"
            description={
              <div style={{ marginTop: 12 }}>
                <div style={{ marginBottom: 8, fontSize: 14 }}>
                  <LoadingOutlined /> {currentFile}
                </div>
                <Progress
                  percent={Math.round(uploadProgress)}
                  status="active"
                  strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
                  size={[300, 12]}
                />
              </div>
            }
            type="info"
            icon={<LoadingOutlined />}
          />
        </div>
      )}

      {/* processing progress */}
      {processing && (
        <div style={{ marginTop: 24 }}>
          <Alert
            message="正在处理文档"
            description={
              <div style={{ marginTop: 12 }}>
                <div style={{ marginBottom: 8, fontSize: 14 }}>
                  <LoadingOutlined spin /> {currentFile || '正在处理...'}
                </div>
                <Progress
                  percent={processingProgress}
                  status={processingProgress < 100 ? 'active' : 'success'}
                  strokeColor={{ '0%': '#108ee9', '100%': '#52c41a' }}
                  size={[300, 12]}
                />
                <div style={{
                  marginTop: 12,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  color: '#666',
                  fontSize: 13
                }}>
                  <span>文档上传成功，正在解析内容...</span>
                  {remainingTime !== null && remainingTime > 0 && (
                    <span style={{ color: '#1890ff', fontWeight: 500 }}>
                      预计剩余: {formatRemainingTime(remainingTime)}
                    </span>
                  )}
                </div>
              </div>
            }
            type="info"
            icon={<LoadingOutlined />}
          />
        </div>
      )}
    </div>
  )

  return (
    <>
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
                  {/* left: folder tree */}
                  <div style={{
                    width: 180,
                    borderRight: `1px solid ${colors.borderLight}`,
                    overflow: 'auto'
                  }}>
                    <FolderTree
                      folders={folders}
                      selectedFolder={selectedFolder}
                      onSelect={setSelectedFolder}
                      onCreate={handleCreateFolder}
                      onRename={handleRenameFolder}
                      onDelete={handleDeleteFolder}
                    />
                  </div>

                  {/* right: file list */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    {/* toolbar */}
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
                      <Button
                        type="primary"
                        icon={<CloudUploadOutlined />}
                        size="small"
                        onClick={() => setActiveTab('upload')}
                      >
                        上传
                      </Button>
                    </div>

                    {/* file list */}
                    <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
                      <FileList
                        files={materials}
                        loading={loading}
                        currentFolder={selectedFolder}
                        onPreview={handleFilePreview}
                        onInsert={handleFileInsert}
                        onLearnProfile={handleLearnProfile}
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
              key: 'upload',
              label: (
                <span>
                  <CloudUploadOutlined />
                  上传
                </span>
              ),
              children: uploadTabContent
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

      {/* file preview modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileTextOutlined style={{ color: colors.primary }} />
            <span>{previewFile?.name || '文件预览'}</span>
          </div>
        }
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            关闭
          </Button>,
          <Button
            key="learn-profile"
            icon={<UserOutlined />}
            loading={learningFileId === previewFile?.id}
            onClick={() => {
              if (previewFile) {
                handleLearnProfile(previewFile)
              }
            }}
          >
            学习为画像
          </Button>,
          <Button
            key="insert"
            type="primary"
            onClick={() => {
              if (previewFile) {
                handleFileInsert(previewFile)
                setPreviewVisible(false)
              }
            }}
          >
            添加引用
          </Button>
        ]}
        width={700}
      >
        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : (
          <div style={{
            maxHeight: 400,
            overflow: 'auto',
            padding: 16,
            background: colors.bgSecondary,
            borderRadius: 8,
            fontSize: 13,
            lineHeight: 1.6
          }}>
            {previewContent?.startsWith('<') || previewContent?.includes('</') || previewContent?.includes('<table') ? (
              <>
                <style>{`
                  .html-preview table { border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: 12px; }
                  .html-preview td, .html-preview th { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
                  .html-preview h2 { font-size: 16px; margin: 16px 0 8px; color: #333; }
                  .html-preview p { margin: 8px 0; }
                `}</style>
                <div
                  className="html-preview"
                  dangerouslySetInnerHTML={{ __html: previewContent }}
                />
              </>
            ) : (
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {previewContent || '无内容'}
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}

export default MaterialDrawer
