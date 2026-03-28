/**
 * UploadDrawer - 上传素材抽屉
 * 支持文件上传进度和处理进度显示
 */
import { useState, useEffect, useRef } from 'react'
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

/** 格式化剩余时间 */
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
  const [processingProgress, setProcessingProgress] = useState(0) // 处理进度百分比
  const [remainingTime, setRemainingTime] = useState<number | null>(null) // 预计剩余时间(秒)
  const [currentFile, setCurrentFile] = useState<string>('')

  // 用于计算剩余时间的计时器
  const processingStartTimeRef = useRef<number | null>(null)
  const processingTimerRef = useRef<NodeJS.Timeout | null>(null)

  // 清理定时器
  useEffect(() => {
    return () => {
      if (processingTimerRef.current) {
        clearInterval(processingTimerRef.current)
        processingTimerRef.current = null
      }
    }
  }, [])

  // 重置状态当抽屉关闭时
  useEffect(() => {
    if (!visible) {
      setUploadProgress(0)
      setProcessingProgress(0)
      setRemainingTime(null)
      if (processingTimerRef.current) {
        clearInterval(processingTimerRef.current)
        processingTimerRef.current = null
      }
    }
  }, [visible])

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
        setProcessingProgress(0)
        setRemainingTime(null)
        processingStartTimeRef.current = Date.now()
        message.loading({ content: '正在处理文档，请稍候...', key: 'processing', duration: 0 })

        // 模拟处理进度（实际应该轮询后端API获取真实进度）
        // 这里模拟一个渐进式的处理过程
        let currentProgress = 0
        const totalSteps = 10
        const stepInterval = 300 // 每步300ms

        processingTimerRef.current = setInterval(() => {
          currentProgress += 100 / totalSteps

          if (currentProgress >= 100) {
            // 处理完成
            clearInterval(processingTimerRef.current!)
            processingTimerRef.current = null
            setProcessingProgress(100)
            setRemainingTime(0)

            setTimeout(() => {
              setProcessing(false)
              message.destroy('processing')
              message.success(`${info.file.name} 处理完成`)
              onUploadComplete?.()
            }, 300)
          } else {
            setProcessingProgress(Math.min(100, Math.round(currentProgress)))

            // 计算预计剩余时间
            if (processingStartTimeRef.current) {
              const elapsed = (Date.now() - processingStartTimeRef.current) / 1000 // 秒
              const progressRatio = currentProgress / 100
              if (progressRatio > 0.05) { // 至少处理了5%才估算
                const totalEstimatedTime = elapsed / progressRatio
                const remaining = totalEstimatedTime - elapsed
                setRemainingTime(Math.max(0, remaining))
              }
            }
          }
        }, stepInterval)
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
                  <LoadingOutlined spin /> {currentFile || '正在处理...'}
                </div>
                <Progress
                  percent={processingProgress}
                  status={processingProgress < 100 ? 'active' : 'success'}
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#52c41a',
                  }}
                  size="large"
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

      {!projectId && (
        <p style={{ color: colors.textTertiary, marginTop: 16 }}>
          请先选择项目
        </p>
      )}
    </Drawer>
  )
}

export default UploadDrawer
