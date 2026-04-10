/**
 * WorkspacePage - 单页面工作台
 * 整合所有功能：编辑器 + AI面板 + 素材/上传/设置抽屉
 * 视觉风格：白色系简洁风格
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchParams } from 'react-router-dom'
import { Select, Button, Space, message, Modal, Input, Tooltip, Popconfirm } from 'antd'
import {
  PlusOutlined, SaveOutlined, UndoOutlined,
  CloudUploadOutlined, DatabaseOutlined, SettingOutlined, RobotOutlined, DeleteOutlined, UserOutlined
} from '@ant-design/icons'
import { useCreationStore } from '../stores/creationStore'
import UploadDrawer from '../components/workspace/UploadDrawer'
import MaterialDrawer from '../components/workspace/MaterialDrawer'
import SettingsDrawer from '../components/workspace/SettingsDrawer'
import ImageInsertDialog from '../components/AICreation/ImageInsertDialog'
import AIChatPanel from '../components/AICreation/AIChatPanel'
import { EmptyStateIllustration } from '../components/Illustrations/RecordingAnimation'
import InlineDiff, { FloatingConfirmBar } from '../components/common/InlineDiff'
import MarkdownTiptapEditor from '../components/common/MarkdownTiptapEditor'
import { markdownToHtml } from '../utils/markdownConverter'
import { colors } from '../styles/design-tokens'
import '../styles/global.css'

interface Project {
  id: number
  name: string
}

const WorkspacePage: React.FC = () => {
  const navigate = useNavigate()
  // URL 参数处理
  const [searchParams, setSearchParams] = useSearchParams()

  // 项目状态
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(() => {
    // 从 URL 参数读取初始项目ID
    const projectIdParam = searchParams.get('project')
    return projectIdParam ? parseInt(projectIdParam, 10) : null
  })
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creating, setCreating] = useState(false)

  // 编辑器状态
  const { setEditorContent, getProjectState, pushEdit, undo, canUndo } = useCreationStore()
  const projectState = currentProjectId ? getProjectState(currentProjectId) : null
  const editorContent = projectState?.editorContent || ''
  const editorRef = useRef<any>(null) // Tiptap Editor 实例
  const canUndoNow = currentProjectId ? canUndo(currentProjectId) : false

  // UI状态
  const [aiPanelVisible, setAiPanelVisible] = useState(false)
  const [uploadDrawerVisible, setUploadDrawerVisible] = useState(false)
  const [materialDrawerVisible, setMaterialDrawerVisible] = useState(false)
  const [settingsDrawerVisible, setSettingsDrawerVisible] = useState(false)
  const [imageModalVisible, setImageModalVisible] = useState(false)

  // AI交互状态
  const [_selectedText, _setSelectedText] = useState('')
  
  // 预览模式状态（智能写作结果预览）
  const [previewMode, setPreviewMode] = useState(false)
  const [previewContent, setPreviewContent] = useState('')
  const [originalBeforePreview, setOriginalBeforePreview] = useState('')

  // 获取项目列表
  const fetchProjects = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/creation/projects')
      if (response.ok) {
        const data = await response.json()
        const list = data.items || data
        setProjects(list)
        // 设置初始项目：优先使用 URL 参数，否则使用第一个项目
        if (list.length > 0 && !currentProjectId) {
          // 检查 URL 参数中的项目ID是否有效
          const urlProjectId = searchParams.get('project')
          const validProject = urlProjectId ? list.find((p: Project) => p.id === parseInt(urlProjectId, 10)) : null
          if (validProject) {
            setCurrentProjectId(validProject.id)
          } else {
            setCurrentProjectId(list[0].id)
          }
        }
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
    }
  }

  // 加载项目内容
  const fetchProjectContent = async (projectId: number) => {
    try {
      console.log('[fetchProjectContent] 开始加载项目内容，projectId:', projectId)
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/content`)
      if (response.ok) {
        const data = await response.json()
        const newContent = data.content || ''
        console.log('[fetchProjectContent] 从后端获取的内容长度:', newContent.length, '前200字符:', newContent.substring(0, 200))
        // 检查内容中的图片URL
        const imageMatches = newContent.match(/!\[([^\]]*)\]\(([^)]+)\)/g)
        if (imageMatches) {
          console.log('[fetchProjectContent] 发现的图片URL:', imageMatches)
        }
        // 检查当前内容，避免覆盖用户正在编辑的内容
        const currentState = getProjectState(projectId)
        if (currentState.editorContent && currentState.editorContent.trim() !== newContent.trim()) {
          console.warn('[fetchProjectContent] ⚠️ 检测到内容差异！当前内容长度:', currentState.editorContent.length, '服务器内容长度:', newContent.length)
          console.warn('[fetchProjectContent] 当前内容前100字符:', currentState.editorContent.substring(0, 100))
          console.warn('[fetchProjectContent] 服务器内容前100字符:', newContent.substring(0, 100))
        }
        setEditorContent(projectId, newContent)
      }
    } catch (error) {
      console.error('[fetchProjectContent] 加载项目内容失败:', error)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  useEffect(() => {
    if (currentProjectId) {
      // 更新 URL 参数以保持同步
      setSearchParams({ project: String(currentProjectId) })

      const state = getProjectState(currentProjectId)
      console.log('[useEffect currentProjectId] 项目切换，当前内容长度:', state.editorContent?.length || 0)
      if (!state.editorContent) {
        console.log('[useEffect currentProjectId] 内容为空，开始加载项目内容')
        fetchProjectContent(currentProjectId)
      } else {
        console.log('[useEffect currentProjectId] 使用已有内容，不重新加载')
      }
    }
  }, [currentProjectId])

  // 自动保存
  useEffect(() => {
    if (!currentProjectId || !editorContent) return
    const timer = setTimeout(() => handleSave(true), 10000)
    return () => clearTimeout(timer)
  }, [editorContent, currentProjectId])

  // 创建项目
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
        await fetchProjects()
        setCurrentProjectId(newProject.id)
      }
    } catch (error) {
      message.error('创建失败')
    } finally {
      setCreating(false)
    }
  }

  // 删除项目
  const handleDeleteProject = async (projectId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        message.success('删除成功')
        // 如果删除的是当前项目，切换到其他项目
        if (currentProjectId === projectId) {
          const remainingProjects = projects.filter(p => p.id !== projectId)
          if (remainingProjects.length > 0) {
            setCurrentProjectId(remainingProjects[0].id)
          } else {
            setCurrentProjectId(null)
          }
        }
        await fetchProjects()
      } else {
        const errorData = await response.json().catch(() => ({ detail: '删除失败' }))
        message.error(errorData.detail || '删除失败')
      }
    } catch (error) {
      console.error('删除项目失败:', error)
      message.error('删除失败，请检查网络连接')
    }
  }

  // 保存
  const handleSave = async (silent = false) => {
    if (!currentProjectId) return
    console.log('[handleSave] 开始保存，内容长度:', editorContent.length, '前100字符:', editorContent.substring(0, 100))
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${currentProjectId}/content`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editorContent })
      })
      if (response.ok) {
        const data = await response.json()
        console.log('[handleSave] 保存成功，服务器返回的updated_at:', data.updated_at)
        // 检查保存后是否需要重新加载内容
        const savedContent = editorContent
        // 延迟检查，看是否有内容被覆盖
        setTimeout(() => {
          const currentState = getProjectState(currentProjectId)
          if (currentState.editorContent !== savedContent) {
            console.warn('[handleSave] ⚠️ 保存后内容被覆盖！保存的内容长度:', savedContent.length, '当前内容长度:', currentState.editorContent.length)
          }
        }, 1000)
        if (!silent) {
          message.success('已保存')
        }
      }
    } catch (error) {
      console.error('[handleSave] 保存失败:', error)
      if (!silent) message.error('保存失败')
    }
  }

  // 编辑器内容变化
  const handleEditorChange = (content: string) => {
    if (currentProjectId) {
      console.log('[handleEditorChange] 编辑器内容变化，长度:', content.length, '前100字符:', content.substring(0, 100))
      setEditorContent(currentProjectId, content)
    }
  }

  // 插入内容到编辑器
  const handleInsertToEditor = (content: string) => {
    if (currentProjectId) {
      const newContent = editorContent + '\n\n' + content
      setEditorContent(currentProjectId, newContent)
      message.success('已添加到编辑器')
    }
  }

  // 直接插入（用于图片）
  const handleDirectInsert = (content: string) => {
    if (currentProjectId && editorRef.current) {
      const editor = editorRef.current
      
      // 如果是 Tiptap 编辑器
      if (editor && typeof editor.chain === 'function') {
        // 检查是否是图片 Markdown 语法
        const imageMatch = content.match(/!\[([^\]]*)\]\(([^)]+)\)/)
        if (imageMatch) {
          const [, alt, url] = imageMatch
          // 处理 URL
          let imageUrl = url.trim().replace(/^["']|["']$/g, '')
          if (imageUrl && !imageUrl.startsWith('http://') && !imageUrl.startsWith('https://')) {
            if (!imageUrl.startsWith('/')) {
              imageUrl = '/' + imageUrl
            }
            imageUrl = `http://localhost:8000${imageUrl}`
          }
          
          // 清理 alt 文本
          const cleanAlt = (alt || '图片').replace(/[\[\]()]/g, '').trim() || '图片'
          
          // 使用 Tiptap 的 setImage 命令插入图片
          // 直接插入图片，Tiptap 会自动处理段落
          editor.chain()
            .focus()
            .setImage({ 
              src: imageUrl, 
              alt: cleanAlt 
            })
            .run()
          
          message.success({
            content: '图片已插入',
            duration: 2
          })
        } else {
          // 普通文本，插入 Markdown 语法
          // 将 Markdown 转换为 HTML 后插入
          const html = markdownToHtml(content)
          editor.chain().focus().insertContent(html).run()
          message.success('已插入')
        }
      } else {
        // 降级方案：直接更新内容（兼容旧代码）
        const newContent = editorContent + (editorContent && !editorContent.endsWith('\n') ? '\n' : '') + content + '\n'
        setEditorContent(currentProjectId, newContent)
        message.success('已插入')
      }
    }
  }

  // 悬浮面板：发送到AI面板

  // 悬浮面板：查询
  const _handleQuery = (text: string, mode: 'local' | 'web') => {
    // TODO: 实现本地/网络查询功能
    message.info(`${mode === 'local' ? '本地' : '网络'}查询: ${text.slice(0, 20)}...`)
  }

  // 悬浮面板：替换选中文字
  const handleReplaceSelection = useCallback((originalText: string, newText: string, start: number, end: number) => {
    if (!currentProjectId) return
    
    // 检查是否是 Tiptap 编辑器
    if (editorRef.current && typeof editorRef.current.chain === 'function') {
      // Tiptap 编辑器：使用 Tiptap API 替换
      const editor = editorRef.current
      const { from, to } = editor.state.selection
      
      // 记录编辑历史（用于撤销）
      pushEdit({
        projectId: currentProjectId,
        type: 'replace',
        originalContent: originalText,
        newContent: newText,
        position: [from, to]
      })
      
      // 使用 Tiptap 命令替换选中内容
      editor.chain()
        .focus()
        .deleteSelection()
        .insertContent(newText)
        .run()
    } else {
      // 传统 textarea：使用字符串替换
      // 记录编辑历史（用于撤销）
      pushEdit({
        projectId: currentProjectId,
        type: 'replace',
        originalContent: originalText,
        newContent: newText,
        position: [start, end]
      })
      
      // 执行替换
      const newContent = editorContent.slice(0, start) + newText + editorContent.slice(end)
      setEditorContent(currentProjectId, newContent)
    }
  }, [currentProjectId, editorContent, pushEdit, setEditorContent, editorRef])

  // 撤销
  const handleUndo = useCallback(() => {
    if (currentProjectId && canUndoNow) {
      undo(currentProjectId)
      message.info('已撤销')
    }
  }, [currentProjectId, canUndoNow, undo])

  // Ctrl+Z 快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        // 只在编辑器聚焦时拦截，否则让浏览器处理
        if (document.activeElement === editorRef.current && canUndoNow) {
          e.preventDefault()
          handleUndo()
        }
      }
      // Esc 取消预览
      if (e.key === 'Escape' && previewMode) {
        handleRejectPreview()
      }
    }
    
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleUndo, canUndoNow, previewMode])

  // 智能写作结果预览 - 由 AIChatPanel 调用
  const handlePreviewContent = useCallback((newContent: string) => {
    if (!currentProjectId) return
    setOriginalBeforePreview(editorContent)
    setPreviewContent(newContent)
    setPreviewMode(true)
  }, [currentProjectId, editorContent])

  // 接受预览内容
  const handleAcceptPreview = useCallback(() => {
    if (!currentProjectId || !previewContent) return
    
    // 记录编辑历史
    pushEdit({
      projectId: currentProjectId,
      type: 'replace',
      originalContent: originalBeforePreview,
      newContent: previewContent,
      position: [0, originalBeforePreview.length]
    })
    
    // 应用内容
    setEditorContent(currentProjectId, previewContent)
    setPreviewMode(false)
    setPreviewContent('')
    setOriginalBeforePreview('')
    message.success('已应用')
  }, [currentProjectId, previewContent, originalBeforePreview, pushEdit, setEditorContent])

  // 拒绝预览内容
  const handleRejectPreview = useCallback(() => {
    setPreviewMode(false)
    setPreviewContent('')
    setOriginalBeforePreview('')
    message.info('已取消')
  }, [])

  return (
    <div style={{ 
      height: '100vh', 
      display: 'flex', 
      flexDirection: 'column',
      background: colors.bgPrimary
    }}>
      {/* 顶部导航栏 - 极简温暖风格 */}
      <nav aria-label="主导航" style={{ 
        height: 56,
        padding: '0 24px',
        borderBottom: `1px solid ${colors.borderLight}`,
        background: colors.bgSecondary,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        {/* 左侧：Logo + 项目选择 */}
        <Space size={16}>
          <div style={{
            fontSize: 18,
            fontWeight: 600,
            color: colors.textPrimary,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <span style={{ fontSize: 24 }}>📄</span>
            <span style={{ fontFamily: '"Playfair Display", Georgia, serif' }}>CraftDoc</span>
          </div>
          
          <div style={{ width: 1, height: 24, background: colors.border }} />
          
          <Select
            style={{ width: 160 }}
            placeholder="选择项目"
            value={currentProjectId}
            onChange={setCurrentProjectId}
            options={projects.map(p => ({ label: p.name, value: p.id }))}
            variant="borderless"
            suffixIcon={null}
          />
          <Tooltip title="新建项目">
            <Button
              type="text"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
              style={{ color: colors.textSecondary }}
            />
          </Tooltip>
          {currentProjectId && (
            <Popconfirm
              title="确定要删除这个项目吗？"
              description="删除后无法恢复，项目中的所有内容将被删除"
              onConfirm={() => handleDeleteProject(currentProjectId)}
              okText="确定"
              cancelText="取消"
            >
              <Tooltip title="删除项目">
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  style={{ color: colors.textSecondary }}
                />
              </Tooltip>
            </Popconfirm>
          )}
          <Tooltip title="保存">
            <Button
              type="text"
              icon={<SaveOutlined />}
              onClick={() => handleSave(false)}
              style={{ color: colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title="撤销 (Ctrl+Z)">
            <Button
              type="text"
              icon={<UndoOutlined />}
              onClick={handleUndo}
              disabled={!canUndoNow}
              style={{ color: canUndoNow ? colors.textSecondary : colors.textTertiary }}
            />
          </Tooltip>
        </Space>

        {/* 右侧：功能入口 */}
        <Space size={8}>
          <Tooltip title="上传素材">
            <Button
              type="text"
              icon={<CloudUploadOutlined />}
              onClick={() => setUploadDrawerVisible(true)}
              style={{ color: colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title="素材库">
            <Button
              type="text"
              icon={<DatabaseOutlined />}
              onClick={() => setMaterialDrawerVisible(true)}
              style={{ color: colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title={aiPanelVisible ? '隐藏' : '显示'}>
            <Button
              type={aiPanelVisible ? 'primary' : 'text'}
              icon={<RobotOutlined />}
              onClick={() => setAiPanelVisible(!aiPanelVisible)}
              style={aiPanelVisible ? {} : { color: colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title="用户画像">
            <Button
              type="text"
              icon={<UserOutlined />}
              onClick={() => navigate('/profile')}
              style={{ color: colors.textSecondary }}
            />
          </Tooltip>
          <Tooltip title="设置">
            <Button
              type="text"
              icon={<SettingOutlined />}
              onClick={() => setSettingsDrawerVisible(true)}
              style={{ color: colors.textSecondary }}
            />
          </Tooltip>
        </Space>
      </nav>

      {/* 主内容区 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* 编辑区 */}
        <div 
          style={{ 
            flex: 1, 
            display: 'flex', 
            flexDirection: 'column',
            position: 'relative',
            background: colors.bgPrimary
          }}
        >
          {/* 编辑器区域 */}
          <div style={{ flex: 1, padding: '24px 48px', overflow: 'auto' }}>
            <div style={{ 
              maxWidth: 800, 
              margin: '0 auto',
              minHeight: '100%'
            }}>
              {/* 空状态展示 */}
              {!currentProjectId || (!editorContent && projects.length === 0) ? (
                <EmptyStateIllustration
                  title="开始工艺文件编辑"
                  description="上传PDF文档，AI 帮你解析并生成工艺文件"
                  action={
                    <Button
                      type="primary"
                      size="large"
                      icon={<PlusOutlined />}
                      onClick={() => setCreateModalVisible(true)}
                      style={{ 
                        background: colors.primary,
                        borderColor: colors.primary,
                        borderRadius: 20,
                        height: 44,
                        paddingLeft: 28,
                        paddingRight: 28
                      }}
                    >
                      创建项目
                    </Button>
                  }
                />
              ) : previewMode ? (
                /* 预览模式 - 显示 InlineDiff */
                <div style={{
                  width: '100%',
                  minHeight: 'calc(100vh - 160px)',
                  padding: 16,
                  background: colors.bgPrimary,
                  borderRadius: 8,
                  border: `2px dashed ${colors.primary}`
                }}>
                  <div style={{ 
                    marginBottom: 16, 
                    padding: '8px 12px',
                    background: `${colors.primary}15`,
                    borderRadius: 8,
                    fontSize: 13,
                    color: colors.textSecondary
                  }}>
                    📝 正在预览 AI 生成内容，按 <kbd style={{ 
                      background: colors.bgSecondary,
                      padding: '2px 6px',
                      borderRadius: 4,
                      margin: '0 4px'
                    }}>Esc</kbd> 取消
                  </div>
                  <InlineDiff
                    original={originalBeforePreview}
                    modified={previewContent}
                    onAccept={handleAcceptPreview}
                    onReject={handleRejectPreview}
                    showActions={false}
                    maxHeight={600}
                  />
                </div>
              ) : (
                /* 编辑模式 - 使用 Tiptap 编辑器（支持内联图片） */
                <MarkdownTiptapEditor
                  key={currentProjectId || 'no-project'}
                  ref={editorRef}
                  value={editorContent}
                  onChange={handleEditorChange}
                  placeholder="开始写作...\n\n💡 选中文字后会出现 AI 工具栏"
                  disabled={!currentProjectId}
                  style={{
                    color: colors.textPrimary
                  }}
                  onOpenImageDialog={() => setImageModalVisible(true)}
                />
              )}
            </div>
          </div>
          
          {/* 预览模式浮动确认栏 */}
          {previewMode && (
            <FloatingConfirmBar
              onAccept={handleAcceptPreview}
              onReject={handleRejectPreview}
              stats={{
                added: previewContent.split('\n').length,
                removed: originalBeforePreview.split('\n').length
              }}
            />
          )}
        </div>

        {/* AI面板 - 可折叠 */}
        {aiPanelVisible && (
          <div style={{ 
            width: 380, 
            borderLeft: `1px solid ${colors.borderLight}`,
            background: colors.bgSecondary,
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <AIChatPanel
                projectId={currentProjectId}
                selectedText={_selectedText}
                onInsertToEditor={handleInsertToEditor}
                onDirectInsert={handleDirectInsert}
                onPreviewContent={handlePreviewContent}
                onClose={() => setAiPanelVisible(false)}
              />
            </div>
          </div>
        )}
      </div>

      {/* 抽屉组件 */}
      <UploadDrawer
        visible={uploadDrawerVisible}
        onClose={() => setUploadDrawerVisible(false)}
        projectId={currentProjectId}
        projectName={projects.find(p => p.id === currentProjectId)?.name}
        onUploadComplete={() => {
          // 刷新素材
        }}
      />

      <MaterialDrawer
        visible={materialDrawerVisible}
        onClose={() => setMaterialDrawerVisible(false)}
        projectId={currentProjectId}
        onInsert={handleInsertToEditor}
      />

      <SettingsDrawer
        visible={settingsDrawerVisible}
        onClose={() => setSettingsDrawerVisible(false)}
      />

      {/* 图片插入对话框 */}
      <ImageInsertDialog
        projectId={currentProjectId}
        visible={imageModalVisible}
        onCancel={() => setImageModalVisible(false)}
        onInsert={handleDirectInsert}
      />

      {/* 创建项目对话框 */}
      <Modal
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20 }}>📝</span>
            新建项目
          </span>
        }
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          setNewProjectName('')
        }}
        onOk={handleCreateProject}
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
        width={420}
        okButtonProps={{
          style: { 
            background: colors.primary, 
            borderColor: colors.primary,
            borderRadius: 20
          }
        }}
        cancelButtonProps={{
          style: { borderRadius: 20 }
        }}
      >
        <div style={{ padding: '20px 0' }}>
          <Input
            placeholder="给项目取个名字..."
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            onPressEnter={handleCreateProject}
            size="large"
            maxLength={50}
            showCount
            autoFocus
            style={{ 
              borderRadius: 12,
              height: 48
            }}
          />
          <p style={{ 
            marginTop: 12, 
            fontSize: 13, 
            color: colors.textTertiary 
          }}>
            💡 项目用于组织你的工艺文档和编辑内容
          </p>
        </div>
      </Modal>
    </div>
  )
}

export default WorkspacePage

