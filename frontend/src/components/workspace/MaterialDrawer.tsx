/**
 * MaterialDrawer - 素材库抽屉
 * Integrated upload, file management, and knowledge scope
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { Drawer, Upload, Button, message, Tabs, Modal, Spin, Progress, Alert } from 'antd'
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

const { Dragger } = Upload

const API_BASE = 'http://localhost:8000/api/creation'
const POLL_INTERVAL = 2000

interface MaterialDrawerProps {
  visible: boolean
  onClose: () => void
  projectId: number | null
  onInsert: (content: string) => void
  /** Open to upload tab on mount */
  defaultTab?: string
  /** When true, render as inline panel instead of floating Drawer */
  inline?: boolean
  /** Notify parent after a working-area toggle succeeded (N6: gate AI input) */
  onWorkingAreaChange?: () => void
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
  defaultTab,
  inline = false,
  onWorkingAreaChange,
}) => {
  const [materials, setMaterials] = useState<MaterialFile[]>([])
  const [loading, setLoading] = useState(false)
  const [folders, setFolders] = useState<FolderNode[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string>('root')
  const [activeTab, setActiveTab] = useState(defaultTab || 'files')

  // preview state
  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewFile, setPreviewFile] = useState<MaterialFile | null>(null)
  const [previewContent, setPreviewContent] = useState<string>('')
  const [previewLoading, setPreviewLoading] = useState(false)

  // profile learning state
  const [learningFileId, setLearningFileId] = useState<number | null>(null)

  // N4 workspace selection: material ids in the project working area
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<Set<number>>(new Set())

  // upload state
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [processingProgress, setProcessingProgress] = useState(0)
  const [remainingTime, setRemainingTime] = useState<number | null>(null)
  const [currentFile, setCurrentFile] = useState<string>('')
  const [pollingMaterialId, setPollingMaterialId] = useState<number | null>(null)

  // batch profile-learning state (N3: folder-level learn-batch SSE)
  const [batchLearn, setBatchLearn] = useState<{ active: boolean; current: number; total: number; file: string }>({
    active: false, current: 0, total: 0, file: '',
  })

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

  // --- Materials ---

  const fetchMaterials = async () => {
    setLoading(true)
    try {
      // Use the real project when available so selected_material_ids
      // reflects its working area; legacy /projects/0 returns [] selection.
      const response = await fetch(`${API_BASE}/projects/${projectId ?? 0}/materials`)
      if (response.ok) {
        const data = await response.json()
        setSelectedMaterialIds(new Set(data.selected_material_ids || []))
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

  // N4: toggle a single material in/out of the project working area.
  // POST /materials is append-semantics (backend skips ids already present),
  // so we only send the delta. Removal only drops the reference.
  const handleToggleMaterialSelect = async (file: MaterialFile) => {
    if (!projectId) return
    const isSelected = selectedMaterialIds.has(file.id)
    // optimistic update
    setSelectedMaterialIds(prev => {
      const next = new Set(prev)
      if (isSelected) {
        next.delete(file.id)
      } else {
        next.add(file.id)
      }
      return next
    })
    try {
      if (isSelected) {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/materials/${file.id}`, {
          method: 'DELETE',
        })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      } else {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/materials`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: projectId, material_ids: [file.id] }),
        })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      }
      onWorkingAreaChange?.()
    } catch {
      message.error(isSelected ? '移出工作区域失败' : '加入工作区域失败')
      fetchMaterials()
    }
  }

  // N4: toggle all files of a folder (root = files without a folder) as a group
  const handleToggleFolderSelect = async (folderKey: string) => {
    if (!projectId) return
    const folderFiles = materials.filter(m =>
      folderKey === 'root' ? !m.folderId : m.folderId === folderKey
    )
    if (folderFiles.length === 0) {
      message.warning('该文件夹无文件')
      return
    }
    const allSelected = folderFiles.every(m => selectedMaterialIds.has(m.id))
    const targets = allSelected
      ? folderFiles.filter(m => selectedMaterialIds.has(m.id))
      : folderFiles.filter(m => !selectedMaterialIds.has(m.id))

    setSelectedMaterialIds(prev => {
      const next = new Set(prev)
      targets.forEach(m => {
        if (allSelected) {
          next.delete(m.id)
        } else {
          next.add(m.id)
        }
      })
      return next
    })

    try {
      if (allSelected) {
        await Promise.all(targets.map(m =>
          fetch(`${API_BASE}/projects/${projectId}/materials/${m.id}`, { method: 'DELETE' })
            .then(resp => {
              if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
            })
        ))
      } else {
        const resp = await fetch(`${API_BASE}/projects/${projectId}/materials`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: projectId, material_ids: targets.map(m => m.id) }),
        })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      }
      message.success(allSelected ? '整组已移出工作区域' : `已加入工作区域 ${targets.length} 个文件`)
      onWorkingAreaChange?.()
    } catch {
      message.error('整组操作失败')
      fetchMaterials()
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

      const resp = await fetch(`http://localhost:8000/api/profile/${file.domain || 'assembly'}/learn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: textContent,
          domain: file.domain || 'assembly',
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

  // N3: batch-learn all files in a folder as profile via SSE stream
  const handleLearnFolder = async (folderKey: string) => {
    const fileIds = materials
      .filter(m => (folderKey === 'root' ? !m.folderId : m.folderId === folderKey))
      .map(m => String(m.id))

    if (fileIds.length === 0) {
      message.warning('该文件夹无可用文件')
      return
    }

    const domain = materials.find(m => String(m.id) === fileIds[0])?.domain || 'assembly'

    setBatchLearn({ active: true, current: 0, total: fileIds.length, file: '' })

    try {
      const resp = await fetch(`http://localhost:8000/api/profile/${domain}/learn-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_ids: fileIds }),
      })

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'start') {
              setBatchLearn({ active: true, current: 0, total: evt.total, file: '' })
            } else if (evt.type === 'progress') {
              setBatchLearn({ active: true, current: evt.current, total: evt.total, file: evt.file })
            } else if (evt.type === 'item_error') {
              message.warning(`跳过 ${evt.file}: ${evt.message}`)
            } else if (evt.type === 'complete') {
              message.success(`批量学习完成 ${evt.ok}/${evt.total},KG ${evt.kg_nodes} 节点`)
              setBatchLearn({ active: false, current: evt.total, total: evt.total, file: '' })
              fetchMaterials()
            }
          } catch {
            // ignore parse errors on partial lines
          }
        }
      }
    } catch (error) {
      console.error('Batch profile learning failed:', error)
      message.error('批量学习出错')
    } finally {
      setBatchLearn(prev => ({ ...prev, active: false }))
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

  const tabItems = [
    {
      key: 'files',
      label: (
        <span>
          <FolderOutlined />
          文件管理
        </span>
      ),
      children: (
        <div style={{ display: 'flex', height: inline ? 'calc(100vh - 200px)' : 'calc(100vh - 150px)' }}>
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
              onLearnFolder={handleLearnFolder}
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
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: colors.textSecondary, fontSize: 13 }}>
                  {selectedFolder === 'root' ? '全部文件' :
                    folders.find(f => f.key === selectedFolder)?.title || '文件'}
                </span>
                {projectId != null && (
                  <Button
                    size="small"
                    onClick={() => handleToggleFolderSelect(selectedFolder)}
                    title="整组加入/移出当前项目的工作区域"
                  >
                    {(() => {
                      const folderFiles = materials.filter(m =>
                        selectedFolder === 'root' ? !m.folderId : m.folderId === selectedFolder
                      )
                      const allSelected = folderFiles.length > 0 &&
                        folderFiles.every(m => selectedMaterialIds.has(m.id))
                      return allSelected ? '整组移出' : '整组勾选'
                    })()}
                  </Button>
                )}
              </div>
            </div>

            {/* file list */}
            <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
              {batchLearn.active && (
                <div style={{ marginBottom: 8 }}>
                  <Alert
                    message="正在批量学习为画像"
                    description={
                      <div style={{ marginTop: 8 }}>
                        <div style={{ marginBottom: 8, fontSize: 14 }}>
                          <LoadingOutlined spin /> 正在学习: {batchLearn.current}/{batchLearn.total}
                          {batchLearn.file ? ` · ${batchLearn.file}` : ''}
                        </div>
                        <Progress
                          percent={batchLearn.total > 0 ? Math.round((batchLearn.current / batchLearn.total) * 100) : 0}
                          status="active"
                          strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
                          size={['100%', 12]}
                        />
                      </div>
                    }
                    type="info"
                    icon={<LoadingOutlined />}
                  />
                </div>
              )}
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
                selectedIds={projectId != null ? selectedMaterialIds : undefined}
                onToggleSelect={projectId != null ? handleToggleMaterialSelect : undefined}
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
    }
  ]

  const tabsElement = (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      style={{ padding: '0 16px' }}
      items={tabItems}
    />
  )

  if (inline) {
    return (
      <>
        <div style={{
          width: 520,
          borderRight: `1px solid ${colors.borderLight}`,
          background: colors.bgPrimary,
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '12px 20px',
            borderBottom: `1px solid ${colors.borderLight}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <DatabaseOutlined style={{ color: colors.primary }} />
              <span style={{ fontWeight: 600, fontSize: 16 }}>素材库</span>
            </div>
            <Button size="small" onClick={onClose}>关闭</Button>
          </div>
          <div style={{ flex: 1, overflow: 'auto' }}>
            {tabsElement}
          </div>
        </div>

        {/* file preview modal — also needed in inline mode */}
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
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                  {previewContent || '无内容'}
                </pre>
              )}
            </div>
          )}
        </Modal>
      </>
    )
  }

  return (
    <>
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <DatabaseOutlined style={{ color: colors.primary }} />
            <span>素材库</span>
          </div>
        }
        placement="left"
        width={520}
        onClose={onClose}
        open={visible}
        styles={{
          body: { padding: 0 }
        }}
      >
        {tabsElement}
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
