/**
 * PortraitUpload - 画像文档上传组件
 * 支持拖拽上传、进度显示、结果预览
 */
import { useState } from 'react'
import { Upload, Button, message, Progress, Card, Typography, Space, Tag, List } from 'antd'
import { UploadOutlined, InboxOutlined, FileTextOutlined } from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd/es/upload'
import { uploadDocumentsAndGeneratePortrait, StylePortrait, PortraitListItem } from '../../services/styleService'

const { Dragger } = Upload
const { Title, Text, Paragraph } = Typography

interface PortraitUploadProps {
  userId: number
  scenarioName?: string
  onUploadSuccess?: (portrait: StylePortrait, portraitId: number) => void
}

export const PortraitUpload: React.FC<PortraitUploadProps> = ({
  userId,
  scenarioName,
  onUploadSuccess
}) => {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [result, setResult] = useState<{
    portrait: StylePortrait
    portraitId: number
    validDocuments: number
    failedFiles?: Array<{ filename: string; reason: string }>
  } | null>(null)

  const handleUpload = async () => {
    if (fileList.length < 3) {
      message.warning('至少需要上传3篇文档')
      return
    }
    if (fileList.length > 20) {
      message.warning('最多只能上传20篇文档')
      return
    }

    setUploading(true)
    setProgress(0)
    setResult(null)

    try {
      // 模拟进度（实际应该由后端SSE提供）
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + 10
        })
      }, 500)

      const files = fileList.map(f => f.originFileObj!).filter(Boolean) as File[]
      
      const response = await uploadDocumentsAndGeneratePortrait(files, userId, scenarioName)
      
      clearInterval(progressInterval)
      setProgress(100)

      setResult({
        portrait: response.portrait,
        portraitId: response.portrait_id,
        validDocuments: response.valid_documents,
        failedFiles: response.failed_files
      })

      message.success(`画像生成成功！置信度: ${(response.confidence_score * 100).toFixed(1)}%`)
      
      if (onUploadSuccess) {
        onUploadSuccess(response.portrait, response.portrait_id)
      }

    } catch (error: any) {
      message.error(error.response?.data?.detail || '上传并生成画像失败')
      console.error('上传失败:', error)
    } finally {
      setUploading(false)
      setTimeout(() => setProgress(0), 2000)
    }
  }

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    accept: '.txt,.docx,.pdf,.doc',
    fileList,
    beforeUpload: (file) => {
      // 不自动上传，由handleUpload控制
      setFileList(prev => [...prev, {
        uid: Date.now().toString(),
        name: file.name,
        status: 'done',
        originFileObj: file
      } as UploadFile])
      return false
    },
    onRemove: (file) => {
      setFileList(prev => prev.filter(f => f.uid !== file.uid))
    }
  }

  return (
    <div>
      <Card>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <Title level={4}>📤 上传文档生成画像</Title>
            <Paragraph type="secondary">
              上传3-20篇您的写作样本（Word/PDF/TXT格式），系统将自动分析并生成六维风格画像
            </Paragraph>
          </div>

          <Dragger {...uploadProps} disabled={uploading}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持 .txt, .docx, .pdf 格式，至少3篇，最多20篇
            </p>
          </Dragger>

          {fileList.length > 0 && (
            <div>
              <Text strong>已选择文件 ({fileList.length}):</Text>
              <List
                size="small"
                dataSource={fileList}
                renderItem={(file) => (
                  <List.Item>
                    <Space>
                      <FileTextOutlined />
                      <Text>{file.name}</Text>
                      <Text type="secondary">
                        ({(file.originFileObj as File)?.size 
                          ? `${((file.originFileObj as File).size / 1024).toFixed(1)} KB`
                          : '未知大小'})
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
            </div>
          )}

          {uploading && (
            <div>
              <Text>正在分析文档并生成画像...</Text>
              <Progress percent={progress} status="active" />
            </div>
          )}

          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={handleUpload}
            loading={uploading}
            disabled={fileList.length < 3 || fileList.length > 20}
            size="large"
            block
          >
            {uploading ? '生成中...' : '开始生成画像'}
          </Button>
        </Space>
      </Card>

      {result && (
        <Card style={{ marginTop: 24 }} title="✅ 生成结果">
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>画像ID: </Text>
              <Text>{result.portraitId}</Text>
            </div>
            <div>
              <Text strong>置信度: </Text>
              <Tag color="green">{(result.portrait.confidence_score * 100).toFixed(1)}%</Tag>
            </div>
            <div>
              <Text strong>版本: </Text>
              <Text>v{result.portrait.version}</Text>
            </div>
            <div>
              <Text strong>来源: </Text>
              <Tag>{result.portrait.source === 'auto' ? '自动生成' : result.portrait.source}</Tag>
            </div>
            <div>
              <Text strong>有效文档: </Text>
              <Text>{result.validDocuments} 篇</Text>
            </div>
            <div>
              <Text strong>风格概述: </Text>
              <Text>{result.portrait.style_overview.summary}</Text>
            </div>

            {result.failedFiles && result.failedFiles.length > 0 && (
              <div>
                <Text strong style={{ color: '#ff4d4f' }}>失败文件:</Text>
                <List
                  size="small"
                  dataSource={result.failedFiles}
                  renderItem={(item) => (
                    <List.Item>
                      <Text type="danger">{item.filename}: {item.reason}</Text>
                    </List.Item>
                  )}
                />
              </div>
            )}
          </Space>
        </Card>
      )}
    </div>
  )
}

export default PortraitUpload
