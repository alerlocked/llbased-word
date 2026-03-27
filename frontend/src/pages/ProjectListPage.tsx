import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Button, Empty, Input, Modal, message, Space, Popconfirm } from 'antd'
import { 
  PlusOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  FileTextOutlined,
  RocketOutlined 
} from '@ant-design/icons'
import { useTheme } from '../contexts/ThemeContext'
import dayjs from 'dayjs'

/**
 * 项目列表页面
 * 显示所有创作项目,支持创建、编辑、删除
 * 为新用户提供清晰的引导
 */

interface Project {
  id: number
  name: string
  created_at: string
  updated_at: string
}

const ProjectListPage: React.FC = () => {
  const navigate = useNavigate()
  const { colors } = useTheme()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')

  /**
   * 加载项目列表
   */
  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/creation/projects')
      if (response.ok) {
        const data = await response.json()
        setProjects(data.items || [])
      } else {
        message.error('加载项目列表失败')
      }
    } catch (error) {
      console.error('加载项目列表失败:', error)
      message.error('网络错误')
    } finally {
      setLoading(false)
    }
  }

  /**
   * 创建新项目
   */
  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      message.warning('请输入项目名称')
      return
    }

    try {
      const response = await fetch('http://localhost:8000/api/creation/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newProjectName.trim() })
      })

      if (response.ok) {
        const data = await response.json()
        message.success('项目创建成功')
        setCreateModalOpen(false)
        setNewProjectName('')
        // 刷新项目列表
        loadProjects()
        // 导航到工作台并选择新项目（通过 URL 参数传递项目ID）
        navigate(`/?project=${data.id}`)
      } else {
        const errorData = await response.json().catch(() => ({ detail: '创建失败' }))
        message.error(errorData.detail || '创建失败')
      }
    } catch (error) {
      console.error('创建项目失败:', error)
      message.error('网络错误，请检查后端服务是否启动')
    }
  }

  /**
   * 删除项目
   */
  const handleDeleteProject = async (projectId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/creation/projects/${projectId}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        message.success('项目已删除')
        loadProjects()
      } else {
        const errorData = await response.json().catch(() => ({ detail: '删除失败' }))
        message.error(errorData.detail || '删除失败')
      }
    } catch (error) {
      console.error('删除项目失败:', error)
      message.error('网络错误，请检查后端服务是否启动')
    }
  }

  /**
   * 进入项目
   */
  const handleEnterProject = (projectId: number) => {
    navigate(`/?project=${projectId}`)
  }

  /**
   * 渲染空状态 - 新手引导
   */
  const renderEmptyState = () => {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 200px)',
        padding: '40px'
      }}>
        <RocketOutlined style={{ fontSize: 80, color: colors.accentPrimary, marginBottom: 24 }} />
        
        <h2 style={{ 
          fontSize: 24, 
          fontWeight: 600, 
          color: colors.textPrimary,
          marginBottom: 16 
        }}>
          欢迎使用工艺文件辅助编辑平台
        </h2>
        
        <p style={{ 
          fontSize: 16, 
          color: colors.textSecondary,
          marginBottom: 32,
          textAlign: 'center',
          maxWidth: 600,
          lineHeight: 1.8
        }}>
          开始你的第一个工艺文件项目吧！<br />
          上传PDF → 智能解析 → 术语对齐 → AI辅助编辑
        </p>

        <Button 
          type="primary" 
          size="large"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalOpen(true)}
          style={{ height: 48, fontSize: 16, paddingLeft: 32, paddingRight: 32 }}
        >
          创建第一个项目
        </Button>

        <div style={{
          marginTop: 48,
          padding: 24,
          backgroundColor: colors.bgSecondary,
          borderRadius: 8,
          maxWidth: 800
        }}>
          <h3 style={{ 
            fontSize: 16, 
            fontWeight: 600, 
            color: colors.textPrimary,
            marginBottom: 16 
          }}>
            💡 快速上手指南
          </h3>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 16,
            color: colors.textSecondary,
            fontSize: 14,
            lineHeight: 1.8
          }}>
            <div>
              <strong style={{ color: colors.textPrimary }}>1️⃣ 上传PDF</strong><br />
              上传工艺文档PDF文件
            </div>
            <div>
              <strong style={{ color: colors.textPrimary }}>2️⃣ 智能解析</strong><br />
              系统自动解析表格和参数
            </div>
            <div>
              <strong style={{ color: colors.textPrimary }}>3️⃣ 创建项目</strong><br />
              在这里创建工艺文件项目
            </div>
            <div>
              <strong style={{ color: colors.textPrimary }}>4️⃣ 术语对齐</strong><br />
              将工艺术语标准化
            </div>
            <div>
              <strong style={{ color: colors.textPrimary }}>5️⃣ AI辅助</strong><br />
              使用AI生成工艺文件
            </div>
            <div>
              <strong style={{ color: colors.textPrimary }}>6️⃣ 完成文件</strong><br />
              编辑润色，导出文档
            </div>
          </div>
        </div>
      </div>
    )
  }

  /**
   * 渲染项目卡片
   */
  const renderProjectCard = (project: Project) => {
    return (
      <Card
        key={project.id}
        hoverable
        style={{
          backgroundColor: colors.bgSecondary,
          borderColor: colors.borderColor
        }}
        actions={[
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEnterProject(project.id)}
          >
            编辑
          </Button>,
          <Popconfirm
            title="确定删除此项目？"
            description="删除后无法恢复"
            onConfirm={() => handleDeleteProject(project.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        ]}
      >
        <Card.Meta
          avatar={<FileTextOutlined style={{ fontSize: 32, color: colors.accentPrimary }} />}
          title={
            <div style={{ 
              fontSize: 18, 
              fontWeight: 600, 
              color: colors.textPrimary,
              marginBottom: 8
            }}>
              {project.name}
            </div>
          }
          description={
            <div style={{ color: colors.textSecondary, fontSize: 14 }}>
              <div>创建时间: {dayjs(project.created_at).format('YYYY-MM-DD HH:mm')}</div>
              <div>最后编辑: {dayjs(project.updated_at).format('YYYY-MM-DD HH:mm')}</div>
            </div>
          }
        />
      </Card>
    )
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题和操作栏 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 24
      }}>
        <div>
          <h1 style={{ 
            fontSize: 28, 
            fontWeight: 600, 
            color: colors.textPrimary,
            margin: 0,
            marginBottom: 8
          }}>
            我的创作项目
          </h1>
          <p style={{ 
            fontSize: 14, 
            color: colors.textSecondary,
            margin: 0
          }}>
            {projects.length > 0 ? `共 ${projects.length} 个项目` : '还没有项目，创建一个开始吧'}
          </p>
        </div>
        
        {projects.length > 0 && (
          <Button 
            type="primary" 
            size="large"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalOpen(true)}
          >
            新建项目
          </Button>
        )}
      </div>

      {/* 项目列表或空状态 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <span>加载中...</span>
        </div>
      ) : projects.length === 0 ? (
        renderEmptyState()
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 24
        }}>
          {projects.map(renderProjectCard)}
        </div>
      )}

      {/* 创建项目对话框 */}
      <Modal
        title="创建新项目"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false)
          setNewProjectName('')
        }}
        onOk={handleCreateProject}
        okText="创建"
        cancelText="取消"
      >
        <div style={{ padding: '20px 0' }}>
          <p style={{ marginBottom: 12, color: colors.textSecondary }}>
            为你的创作项目起个名字
          </p>
          <Input
            placeholder="例如: 轴类零件加工工艺、装配工艺卡片..."
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
    </div>
  )
}

export default ProjectListPage

