/**
 * UploadDrawer - 上传素材抽屉
 */
import { useState } from 'react'
import { Drawer, Upload, Button, message, Space, Progress, Alert } from 'antd'
import { InboxOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

const { Dragger } = Upload

interface UploadDrawerProps {
  visible: boolean
  onClose: () => void
  projectId: number | null
  projectName?: string
  onUploadComplete?: () => void
}

const UploadDrawer: React.FC<UploadDrawerProps> = ({
  visible,
  onClose,
  projectId,
  projectName,
  onUploadComplete
}) => {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [processing, setProcessing] = useState(false)
  const [currentFile, setCurrentFile] = useState<string>('')

  const uploadProps = {
    name: 'file',
    multiple: false,
    action: `http://localhost:8000/api/creation/projects/${projectId}/documents`,
    showUploadList: false,
    onChange(info: any) {
      setCurrentFile(info.file.name)
      
      if (info.file.status === 'uploading') {
        setUploading(true)
        setUploadProgress(info.file.percent || 0)
      }
      
      if (info.file.status === 'done') {
        setUploading(false)
        setProcessing(true)
        message.loading({ content: '正在处理文档，请稍候...', key: 'processing', duration: 0 })
        
        // 模拟处理进度（实际应该轮询后端API）
        setTimeout(() => {
          setProcessing(false)
          message.destroy('processing')
          message.success(`${info.file.name} 处理完成`)
          onUploadComplete?.()
        }, 2000)
      } 
      
      if (info.file.status === 'error') {
        setUploading(false)
        setProcessing(false)
        message.error(`${info.file.name} 上传失败`)
      }
    },
    onDrop(e: DragEvent) {
      // 处理拖放
    }
  }

  return (
    <Drawer
      title={`上传素材 - ${projectName || '未选择项目'}`}
      placement="right"
      width={400}
      onClose={onClose}
      open={visible}
    >
      {/* 上传区域 */}
      <Dragger {...uploadProps} disabled={!projectId || uploading || processing}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ color: colors.primary, fontSize: 48 }} />
        </p>
        <p className="ant-upload-text" style={{ fontSize: 16, fontWeight: 500 }}>
          点击或拖拽文件到此区域上传
        </p>
        <p className="ant-upload-hint">支持图片、PDF等格式</p>
      </Dragger>

      {/* 上传进度 */}
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
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#87d068',
                  }}
                  size="large"
                />
              </div>
            }
            type="info"
            icon={<LoadingOutlined />}
          />
        </div>
      )}

      {/* 处理进度 */}
      {processing && (
        <div style={{ marginTop: 24 }}>
          <Alert
            message="正在处理文档"
            description={
              <div style={{ marginTop: 12 }}>
                <div style={{ marginBottom: 8, fontSize: 14 }}>
                  <LoadingOutlined /> {currentFile}
                </div>
                <Progress 
                  percent={100}
                  status="active"
                  strokeColor="#52c41a"
                  size="large"
                />
                <div style={{ marginTop: 8, color: '#666', fontSize: 13 }}>
                  文档上传成功，正在解析内容...
                </div>
              </div>
            }
            type="success"
            icon={<CheckCircleOutlined />}
          />
        </div>
      )}

      {!projectId && (
        <p style={{ color: colors.textTertiary, marginTop: 16 }}>
          请先选择项目
        </p>
      )}
    </Drawer>
  )
}

export default UploadDrawer
