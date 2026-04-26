/**
 * UploadDrawer - 上传素材抽屉
 * 支持文件上传进度和真实解析进度轮询
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { Drawer, Upload, Button, message, Progress, Alert } from 'antd'
import { InboxOutlined, LoadingOutlined } from '@ant-design/icons'
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

const POLL_INTERVAL = 2000

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
  const [processingProgress, setProcessingProgress] = useState(0)
  const [remainingTime, setRemainingTime] = useState<number | null>(null)
  const [currentFile, setCurrentFile] = useState<string>('')
  const [pollingMaterialId, setPollingMaterialId] = useState<number | null>(null)

  const processingStartTimeRef = useRef<number | null>(null)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Poll parse status
  const pollParseStatus = useCallback(async (materialId: number) => {
    try {
      const resp = await fetch(`http://localhost:8000/api/creation/materials/${materialId}/parse-status`)
      if (!resp.ok) return
      const data = await resp.json()

      setProcessingProgress(data.progress || 0)

      // Estimate remaining time
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
          onUploadComplete?.()
        }, 300)
      } else if (data.status === 'failed') {
        stopPolling()
        setProcessing(false)
        message.destroy('processing')
        message.error(`${currentFile} 解析失败: ${data.error_message || '未知错误'}`)
        onUploadComplete?.()
      }
    } catch {
      // Network error, keep polling
    }
  }, [currentFile, onUploadComplete])

  const startPolling = useCallback((materialId: number) => {
    stopPolling()
    pollTimerRef.current = setInterval(() => {
      pollParseStatus(materialId)
    }, POLL_INTERVAL)
  }, [pollParseStatus])

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  // Reset on drawer close
  useEffect(() => {
    if (!visible) {
      setUploadProgress(0)
      setProcessingProgress(0)
      setRemainingTime(null)
      setPollingMaterialId(null)
      stopPolling()
    }
  }, [visible, stopPolling])

  // Start polling when materialId is set
  useEffect(() => {
    if (pollingMaterialId !== null && processing) {
      startPolling(pollingMaterialId)
      // Fire first poll immediately
      pollParseStatus(pollingMaterialId)
    }
    return () => stopPolling()
  }, [pollingMaterialId])

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
        message.loading({ content: '正在解析文档，请稍候...', key: 'processing', duration: 0 })

        // Extract material_id from response and start polling
        const materialId = info.file.response?.material_id
        if (materialId) {
          setPollingMaterialId(materialId)
        } else {
          // Fallback: no material_id returned, show generic progress
          setProcessingProgress(10)
        }
      }

      if (info.file.status === 'error') {
        setUploading(false)
        setProcessing(false)
        message.error(`${info.file.name} 上传失败`)
      }
    },
    onDrop(e: DragEvent) {
      // handle drop
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
