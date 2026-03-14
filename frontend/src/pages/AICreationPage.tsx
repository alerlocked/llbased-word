/**
 * AICreationPage - AI创作页面（三栏布局）
 * 左侧：素材库面板 | 中间：富文本编辑器 | 右侧：AI交互面板
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Layout, Select, Button, Space, message, Modal, Input } from 'antd'
import { PlusOutlined, SaveOutlined } from '@ant-design/icons'
import MainLayout from '../components/Layout/MainLayout'
import MaterialsPanel from '../components/AICreation/MaterialsPanel'
import EditorPanel from '../components/AICreation/EditorPanel'
import AIChatPanel from '../components/AICreation/AIChatPanel'
import { useCreationStore } from '../stores/creationStore'

const { Content } = Layout

interface Project {
  id: number
  name: string
}

const AICreationPage: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(null)
  
  const { setEditorContent, getProjectState } = useCreationStore()
  const projectState = currentProjectId ? getProjectState(currentProjectId) : null
  const editorContent = projectState?.editorContent || ''
  
  const [selectedText, setSelectedText] = useState('')
  const [proposedContent, setProposedContent] = useState<string | null>(null)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creating, setCreating] = useState(false)
  
  // 右侧栏宽度（可拖拽调整）
  const [rightPanelWidth, setRightPanelWidth] = useState(() => {
    const saved = localStorage.getItem('ai_chat_panel_width')
    return saved ? parseInt(saved, 10) : 400
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeStartX = useRef(0)
  const resizeStartWidth = useRef(400)

  // 打开创建对话框
  const handleOpenCreateModal = () => {
    setCreateModalVisible(true)
  }

  // 创建新项目
  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      message.warning('请输入项目名称')
      return
    }

    setCreating(true)
    try {
      const response = await fetch('http://localhost:8000/api/creation/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newProjectName })
      })

      if (response.ok) {
        const newProject = await response.json()
        message.success('创建成功')
        setCreateModalVisible(false)
        setNewProjectName('')
        
        // 刷新列表并选中新项目
        await fetchProjects()
        setCurrentProjectId(newProject.id)
      } else {
        message.error('创建失败')
      }
    } catch (error) {
      console.error('创建项目失败:', error)
      message.error('网络错误')
    } finally {
      setCreating(false)
    }
  }

  // 更新编辑器内容的封装函数
  const handleEditorChange = (content: string) => {
    if (currentProjectId) {
      setEditorContent(currentProjectId, content)
    }
  }

  // 获取项目列表
  const fetchProjects = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/creation/projects')
      if (response.ok) {
        const data = await response.json()
        const projectList = data.items || data
        setProjects(projectList)
        if (projectList.length > 0 && !currentProjectId) {
          setCurrentProjectId(projectList[0].id)
        }
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  // 当项目切换时，加载项目内容（如果本地没有的话）
  useEffect(() => {
    if (currentProjectId) {
      const state = getProjectState(currentProjectId)
      if (!state.editorContent) {
        fetchProjectContent(currentProjectId)
      }
    }
  }, [currentProjectId])

  // 加载项目内容
  const fetchProjectContent = async (projectId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/content`)
      if (response.ok) {
        const data = await response.json()
        setEditorContent(projectId, data.content || '')
      }
    } catch (error) {
      console.error('加载项目内容失败:', error)
    }
  }

  // 自动保存逻辑
  useEffect(() => {
    if (!currentProjectId || !editorContent) return

    const timer = setTimeout(() => {
      handleSave(true) // 静默保存
    }, 10000)

    return () => clearTimeout(timer)
  }, [editorContent, currentProjectId])

  // 保存编辑内容
  const handleSave = async (silent = false) => {
    if (!currentProjectId) {
      if (!silent) message.warning('请先选择或创建项目')
      return
    }

    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${currentProjectId}/content`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editorContent })
      })

      if (response.ok) {
        if (!silent) message.success('保存成功')
      } else {
        if (!silent) message.error('保存失败')
      }
    } catch (error) {
      console.error('保存失败:', error)
      if (!silent) message.error('网络错误')
    }
  }

  // 处理文本选中
  const handleTextSelect = (text: string) => {
    setSelectedText(text)
  }

  // 从素材插入到编辑器 (改为建议模式)
  const handleInsertMaterial = (content: string) => {
    setProposedContent(content)
  }

  // 直接插入内容 (用于图片等)
  const handleDirectInsert = (content: string) => {
    if (currentProjectId) {
      // 简单追加到末尾，或者需要在光标处插入（这需要EditorPanel支持）
      // 目前 EditorPanel 受控于 editorContent
      // 如果要支持光标插入，EditorPanel 需要暴露 insertAtCursor 方法
      // 暂时简单追加，或者替换选中文本
      // 由于无法获取光标位置，这里追加到末尾
      const newContent = editorContent + '\n' + content
      setEditorContent(currentProjectId, newContent)
      message.success('已插入')
    }
  }

  // 接受 AI 建议
  const handleAcceptProposal = (newContent: string) => {
    if (currentProjectId) {
      setEditorContent(currentProjectId, newContent)
      setProposedContent(null)
      message.success('已落实修改')
    }
  }

  // 拒绝 AI 建议
  const handleRejectProposal = () => {
    setProposedContent(null)
  }

  // 拖拽调整右侧栏宽度（使用闭包处理，避免依赖问题）

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsResizing(true)
    resizeStartX.current = e.clientX
    resizeStartWidth.current = rightPanelWidth

    let currentWidth = rightPanelWidth

    const onMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = resizeStartX.current - moveEvent.clientX
      currentWidth = Math.max(200, Math.min(500, resizeStartWidth.current + deltaX))
      setRightPanelWidth(currentWidth)
    }

    const onMouseUp = () => {
      setIsResizing(false)
      localStorage.setItem('ai_chat_panel_width', currentWidth.toString())
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [rightPanelWidth])

  return (
    <MainLayout>
      <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
        {/* 顶部工具栏 */}
        <div style={{ 
          padding: '16px 24px', 
          borderBottom: '1px solid #f0f0f0',
          background: '#fff'
        }}>
          <Space>
            <span style={{ fontWeight: 500 }}>当前项目：</span>
            <Select
              style={{ width: 200 }}
              placeholder="选择项目"
              value={currentProjectId}
              onChange={setCurrentProjectId}
              options={projects.map(p => ({ label: p.name, value: p.id }))}
            />
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={handleOpenCreateModal}
            >
              新建项目
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
            >
              保存
            </Button>
          </Space>
        </div>

        {/* 三栏布局 */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* 左侧：素材库面板 */}
          <div style={{ 
            width: 280, 
            borderRight: '1px solid #f0f0f0',
            overflow: 'auto',
            background: '#fafafa'
          }}>
            <MaterialsPanel
              projectId={currentProjectId}
              onInsert={handleInsertMaterial}
            />
          </div>

          {/* 中间：编辑器 */}
          <div style={{ flex: 1, overflow: 'auto', background: '#fff' }}>
            <EditorPanel
              content={editorContent}
              proposedContent={proposedContent || undefined}
              onChange={handleEditorChange}
              onTextSelect={handleTextSelect}
              onAccept={handleAcceptProposal}
              onReject={handleRejectProposal}
              projectId={currentProjectId || undefined}
            />
          </div>

          {/* 右侧：AI交互面板（可拖拽调整宽度） */}
          <div style={{ 
            width: rightPanelWidth, 
            position: 'relative',
            borderLeft: '1px solid #f0f0f0',
            background: '#fff',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* 拖拽手柄 */}
            <div
              onMouseDown={handleResizeStart}
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: 0,
                width: 4,
                cursor: 'col-resize',
                backgroundColor: 'transparent',
                zIndex: 10,
                transition: isResizing ? 'none' : 'background-color 0.2s'
              }}
              onMouseEnter={(e) => {
                if (!isResizing) {
                  e.currentTarget.style.backgroundColor = '#1890ff'
                }
              }}
              onMouseLeave={(e) => {
                if (!isResizing) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                }
              }}
            />
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <AIChatPanel
                projectId={currentProjectId}
                selectedText={selectedText}
                onInsertToEditor={handleInsertMaterial}
                onDirectInsert={handleDirectInsert}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 创建项目对话框 */}
      <Modal
        title="创建新项目"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          setNewProjectName('')
        }}
        onOk={handleCreateProject}
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
      >
        <div style={{ padding: '20px 0' }}>
          <p style={{ marginBottom: 12, color: '#666' }}>
            为你的创作项目起个名字
          </p>
          <Input
            placeholder="例如: 乡村振兴报道、人物专访稿..."
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            onPressEnter={handleCreateProject}
            size="large"
            maxLength={50}
            showCount
            autoFocus
          />
        </div>
      </Modal>
    </MainLayout>
  )
}

export default AICreationPage

