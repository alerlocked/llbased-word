/**
 * UploadDrawer - 上传素材抽屉
 */
import { useState } from 'react'
import { Drawer, Upload, Button, message, Space } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
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

  const uploadProps = {
    name: 'file',
    multiple: true,
    action: `http://localhost:8000/api/creation/projects/${projectId}/upload`,
    onChange(info: any) {
      if (info.file.status === 'done') {
        message.success(`${info.file.name} 上传成功`)
        onUploadComplete?.()
      } else if (info.file.status === 'error') {
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
      <Dragger {...uploadProps} disabled={!projectId}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ color: colors.primary }} />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">支持图片、PDF等格式</p>
      </Dragger>

      {!projectId && (
        <p style={{ color: colors.textTertiary, marginTop: 16 }}>
          请先选择项目
        </p>
      )}
    </Drawer>
  )
}

export default UploadDrawer
