import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Button, message, Space, Input, Modal, Tabs } from 'antd'
import { SaveOutlined, FileWordOutlined, HistoryOutlined, MessageOutlined, EditOutlined } from '@ant-design/icons'
import { useTheme } from '../contexts/ThemeContext'
import MaterialPanel from '../components/Creation/MaterialPanel'
import EditorPanel from '../components/Creation/EditorPanel'
import AIDialog, { AIDialogType } from '../components/Creation/AIDialog'
import ContextMenu from '../components/Creation/ContextMenu'
import VersionHistory from '../components/Creation/VersionHistory'
import DiffHighlight from '../components/Creation/DiffHighlight'
import AddMaterialDialog from '../components/common/AddMaterialDialog'
import { ConversationPanel } from '../components/AICreation/ConversationPanel'

/**
 * 创作页面
 * 双面板布局: 素材面板(左) + 编辑器面板(右)
 * 支持AI辅助写作、右键菜单、快捷键等功能
 */

const CreationPage: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>()
  const { colors } = useTheme()
  
  // 状态管理
  const [projectName, setProjectName] = useState('新项目')
  const [editorContent, setEditorContent] = useState('')
  const [oldContent, setOldContent] = useState('') // 用于差异显示
  const [documentMaterials, setDocumentMaterials] = useState<any[]>([])
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  
  // AI对话框状态
  const [aiDialogOpen, setAiDialogOpen] = useState(false)
  const [aiDialogType, setAiDialogType] = useState<AIDialogType>('draft')
  const [selectedText, setSelectedText] = useState('')
  
  // 右键菜单状态
  const [contextMenuVisible, setContextMenuVisible] = useState(false)
  const [contextMenuPos, setContextMenuPos] = useState({ x: 0, y: 0 })
  
  // 版本历史状态
  const [versionHistoryVisible, setVersionHistoryVisible] = useState(false)
  
  // 差异显示状态
  const [showDiff, setShowDiff] = useState(false)
  
  // 添加素材对话框
  const [addMaterialDialogOpen, setAddMaterialDialogOpen] = useState(false)
  
  // 创作模式：'traditional' | 'conversation'
  const [creationMode, setCreationMode] = useState<'traditional' | 'conversation'>('traditional')
  
  const editorRef = useRef<HTMLDivElement>(null)

  /**
   * 初始化项目
   */
  useEffect(() => {
    if (projectId) {
      loadProject(parseInt(projectId))
    }
  }, [projectId])

  /**
   * 快捷键处理
   */
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Shift+G: 生成初稿
      if (e.ctrlKey && e.shiftKey && e.key === 'G') {
        e.preventDefault()
        handleOpenAIDialog('draft')
      }
      // Ctrl+Shift+S: 综合检索
      else if (e.ctrlKey && e.shiftKey && e.key === 'S') {
        e.preventDefault()
        handleOpenAIDialog('search')
      }
      // Ctrl+Shift+Q: 提问
      else if (e.ctrlKey && e.shiftKey && e.key === 'Q') {
        e.preventDefault()
        handleOpenAIDialog('ask')
      }
      // Ctrl+Shift+R: 改写
      else if (e.ctrlKey && e.shiftKey && e.key === 'R') {
        e.preventDefault()
        if (selectedText) {
          handleOpenAIDialog('rewrite')
        }
      }
      // Ctrl+Shift+E: 扩写
      else if (e.ctrlKey && e.shiftKey && e.key === 'E') {
        e.preventDefault()
        if (selectedText) {
          handleOpenAIDialog('expand')
        }
      }
      // Ctrl+Shift+C: 精简
      else if (e.ctrlKey && e.shiftKey && e.key === 'C') {
        e.preventDefault()
        if (selectedText) {
          handleOpenAIDialog('simplify')
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedText])

  /**
   * 处理文本选择
   */
  useEffect(() => {
    const handleSelection = () => {
      const selection = window.getSelection()
      if (selection && selection.toString().trim()) {
        setSelectedText(selection.toString().trim())
      } else {
        setSelectedText('')
      }
    }

    document.addEventListener('selectionchange', handleSelection)
    return () => document.removeEventListener('selectionchange', handleSelection)
  }, [])

  /**
   * 加载项目数据
   */
  const loadProject = async (id: number) => {
    setLoading(true)
    try {
      // 加载项目素材
      const response = await fetch(`http://localhost:8000/api/creation/projects/${id}/materials`)
      if (response.ok) {
        const data = await response.json()
        setDocumentMaterials(data.documents || [])
        setSearchResults(data.searches || [])
      }
    } catch (error) {
      message.error('加载项目失败')
    } finally {
      setLoading(false)
    }
  }

  /**
   * 保存项目
   */
  const handleSave = async () => {
    try {
      // TODO: 调用API保存项目
      message.success('保存成功')
    } catch (error) {
      message.error('保存失败')
    }
  }

  /**
   * 导出Word
   */
  const handleExportWord = async () => {
    try {
      // TODO: 调用API导出Word
      message.info('Word导出功能开发中')
    } catch (error) {
      message.error('导出失败')
    }
  }

  /**
   * 打开AI对话框
   */
  const handleOpenAIDialog = (type: AIDialogType) => {
    setAiDialogType(type)
    setAiDialogOpen(true)
  }

  /**
   * 处理AI操作确认
   */
  const handleAIConfirm = async (params: any) => {
    try {
      let response: Response
      let url = 'http://localhost:8000/api/creation/'

      switch (aiDialogType) {
        case 'draft':
          url += 'generate-draft'
          response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
          })
          break
        case 'search':
          url += 'comprehensive-search'
          response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...params, context: editorContent })
          })
          break
        case 'ask':
          url += 'ask'
          response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...params, context: editorContent })
          })
          break
        case 'rewrite':
        case 'expand':
        case 'simplify':
          url += 'text-operation'
          response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
          })
          break
        default:
          return
      }

      if (response.ok) {
        const data = await response.json()

        if (aiDialogType === 'draft') {
          // 生成初稿: 替换编辑器内容并显示差异
          setOldContent(editorContent)
          setEditorContent(data.content)
          setShowDiff(true)
          message.success('初稿已生成')
        } else if (aiDialogType === 'search') {
          // 综合检索: 添加检索结果到素材面板
          const newResults = (data || []).map((item: any, index: number) => ({
            id: Date.now() + index,
            title: item.title,
            content: item.content,
            source: item.source,
            searchType: 'web' as const,
            createdAt: new Date().toISOString()
          }))
          setSearchResults(prev => [...prev, ...newResults])
          message.success(`已添加${newResults.length}条检索结果`)
        } else if (aiDialogType === 'ask') {
          // 提问: 显示回答
          Modal.info({
            title: 'AI回答',
            content: data.answer,
            width: 600
          })
        } else {
          // 改写/扩写/精简: 替换选中文本并显示差异
          setOldContent(selectedText)
          // TODO: 在编辑器中替换选中文本
          setShowDiff(true)
          message.success('操作完成')
        }
      } else {
        throw new Error('操作失败')
      }
    } catch (error) {
      message.error('操作失败')
    }
  }

  /**
   * 处理右键菜单
   */
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    setContextMenuPos({ x: e.clientX, y: e.clientY })
    setContextMenuVisible(true)
  }

  /**
   * 处理右键菜单选择
   */
  const handleMenuClick = (key: string) => {
    setContextMenuVisible(false)
    handleOpenAIDialog(key as AIDialogType)
  }
  
  /**
   * 处理编辑器右键菜单
   */
  const handleEditorContextMenu = (event: React.MouseEvent, text: string) => {
    event.preventDefault()
    setSelectedText(text)
    setContextMenuPos({ x: event.clientX, y: event.clientY })
    setContextMenuVisible(true)
  }

  /**
   * 处理版本回滚
   */
  const handleRollback = async (versionId: number) => {
    try {
      if (!projectId) return
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/rollback/${versionId}`, {
        method: 'POST'
      })
      if (response.ok) {
        await loadProject(parseInt(projectId))
        message.success('已回滚到该版本')
      }
    } catch (error) {
      message.error('回滚失败')
    }
  }

  /**
   * 打开添加素材对话框
   */
  const handleAddMaterial = () => {
    setAddMaterialDialogOpen(true)
  }

  /**
   * 确认添加素材
   */
  const handleConfirmAddMaterial = async (selectedIds: number[]) => {
    if (!projectId) {
      message.warning('请先创建项目')
      return
    }
    
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: parseInt(projectId),
          material_ids: selectedIds
        })
      })
      
      if (response.ok) {
        message.success('素材添加成功')
        setAddMaterialDialogOpen(false)
        await loadProject(parseInt(projectId))
      } else {
        message.error('添加失败')
      }
    } catch (error) {
      message.error('添加失败')
    }
  }

  /**
   * 删除素材
   */
  const handleRemoveMaterial = async (materialId: number) => {
    if (!projectId) return
    
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/materials/${materialId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        message.success('素材已移除')
        await loadProject(parseInt(projectId))
      } else {
        message.error('移除失败')
      }
    } catch (error) {
      message.error('移除失败')
    }
  }

  return (
    <div
      style={{
        height: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: colors.bgPrimary
      }}
      onContextMenu={handleContextMenu}
    >
      {/* 顶部工具栏 */}
      <div
        style={{
          padding: '12px 24px',
          backgroundColor: colors.bgSecondary,
          borderBottom: `1px solid ${colors.borderColor}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <Space>
          <Input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="项目名称"
            style={{ width: 300 }}
            variant="borderless"
          />
          <Tabs
            activeKey={creationMode}
            onChange={(key) => setCreationMode(key as 'traditional' | 'conversation')}
            size="small"
            items={[
              {
                key: 'traditional',
                label: (
                  <span>
                    <EditOutlined /> 传统模式
                  </span>
                )
              },
              {
                key: 'conversation',
                label: (
                  <span>
                    <MessageOutlined /> 对话式创作
                  </span>
                )
              }
            ]}
          />
        </Space>
        <Space>
          <Button icon={<HistoryOutlined />} onClick={() => setVersionHistoryVisible(true)}>
            版本历史
          </Button>
          <Button icon={<SaveOutlined />} onClick={handleSave}>
            保存
          </Button>
          <Button icon={<FileWordOutlined />} onClick={handleExportWord}>
            导出Word
          </Button>
        </Space>
      </div>

      {/* 主内容区 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {creationMode === 'conversation' ? (
          /* 对话式创作模式 */
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <ConversationPanel
              projectId={projectId ? parseInt(projectId) : undefined}
              userId={1} // TODO: 从用户上下文获取
              initialInput={editorContent}
              onComplete={(content) => {
                setEditorContent(content)
                setCreationMode('traditional') // 完成后切换回传统模式
                message.success('内容已生成')
              }}
            />
          </div>
        ) : (
          /* 传统模式 */
          <>
            {/* 左侧: 素材面板 */}
            <div style={{ width: 400, borderRight: `1px solid ${colors.borderColor}` }}>
              <MaterialPanel
                projectId={projectId ? parseInt(projectId) : undefined}
                documentMaterials={documentMaterials}
                searchResults={searchResults}
                onAddMaterial={handleAddMaterial}
                onRemoveMaterial={handleRemoveMaterial}
                onMaterialsUpdate={setDocumentMaterials}
              />
            </div>

            {/* 右侧: 编辑器面板 */}
            <div
              ref={editorRef}
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              {showDiff && oldContent ? (
                <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
                  <DiffHighlight 
                    oldContent={oldContent} 
                    newContent={editorContent}
                    onAccept={() => {
                      setShowDiff(false)
                      setOldContent('')
                      message.success('已接受修改')
                    }}
                    onReject={() => {
                      setEditorContent(oldContent)
                      setShowDiff(false)
                      setOldContent('')
                      message.info('已撤销修改')
                    }}
                  />
                </div>
              ) : (
                <EditorPanel
                  content={editorContent}
                  onChange={setEditorContent}
                  onContextMenu={handleEditorContextMenu}
                  placeholder="开始编写工艺文件内容..."
                  projectId={projectId ? parseInt(projectId) : undefined}
                />
              )}
            </div>
          </>
        )}
      </div>

      {/* AI对话框 */}
      <AIDialog
        open={aiDialogOpen}
        type={aiDialogType}
        initialContent={selectedText || editorContent}
        onClose={() => setAiDialogOpen(false)}
        onConfirm={handleAIConfirm}
      />

      {/* 右键菜单 */}
      <ContextMenu
        visible={contextMenuVisible}
        x={contextMenuPos.x}
        y={contextMenuPos.y}
        selectedText={selectedText}
        onMenuClick={handleMenuClick}
        onClose={() => setContextMenuVisible(false)}
      />

      {/* 添加素材对话框 */}
      <AddMaterialDialog
        visible={addMaterialDialogOpen}
        onCancel={() => setAddMaterialDialogOpen(false)}
        onConfirm={handleConfirmAddMaterial}
        existingMaterialIds={documentMaterials.map(m => m.id)}
      />

      {/* 版本历史 */}
      {projectId && (
        <VersionHistory
          projectId={parseInt(projectId)}
          visible={versionHistoryVisible}
          onClose={() => setVersionHistoryVisible(false)}
          onRollback={handleRollback}
        />
      )}
    </div>
  )
}

export default CreationPage
