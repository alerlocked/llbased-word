/**
 * SelectionDialog — modal for viewing, editing, and acting on selected text.
 *
 * Opens when user selects text in a template table cell and clicks the
 * floating "📎 处理选区" button. Provides:
 *  - Read-only original text display with length counter
 *  - Editable TextArea pre-filled with original
 *  - Actions: 发送给AI对话 / 替换原文 / 复制 / AI润色 / AI审查 / AI补齐 / AI校对
 */
import { useEffect, useState } from 'react'
import { Modal, Input, Button, Tag, message, Spin, Collapse, Typography } from 'antd'
import {
  SendOutlined,
  EditOutlined,
  CopyOutlined,
  BulbOutlined,
  SafetyCertificateOutlined,
  FileAddOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import type { CellInfo } from '../../types/template'

const { TextArea } = Input
const { Text } = Typography

export interface SelectionDialogProps {
  open: boolean
  selectedText: string
  cellInfo: CellInfo | null
  maxLength: number
  onClose: () => void
  onSendToChat: (text: string) => void
  onReplaceCell: (cellInfo: CellInfo, newText: string) => void
  onPolish: (text: string) => Promise<string>
  onReview: (text: string) => Promise<string>
  onFill: (text: string) => Promise<string>
  onProofread: (text: string) => Promise<string>
}

const SelectionDialog: React.FC<SelectionDialogProps> = ({
  open,
  selectedText,
  cellInfo,
  maxLength,
  onClose,
  onSendToChat,
  onReplaceCell,
  onPolish,
  onReview,
  onFill,
  onProofread,
}) => {
  const [editedText, setEditedText] = useState(selectedText)
  const [polishLoading, setPolishLoading] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [fillLoading, setFillLoading] = useState(false)
  const [proofreadLoading, setProofreadLoading] = useState(false)
  const [reviewResult, setReviewResult] = useState<string | null>(null)

  // Sync editedText when dialog opens with new selectedText
  useEffect(() => {
    if (open) {
      setEditedText(selectedText)
      setReviewResult(null)
    }
  }, [open, selectedText])

  const isOverLimit = editedText.length > maxLength
  const charCountColor = isOverLimit ? '#dc3545' : '#999'

  const handleSendToChat = () => {
    onSendToChat(editedText)
    message.success('已发送到AI对话')
    onClose()
  }

  const handleReplaceCell = () => {
    if (!cellInfo) return
    onReplaceCell(cellInfo, editedText)
    message.success('已替换原文')
    onClose()
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(editedText)
      message.success('已复制到剪贴板')
    } catch {
      message.error('复制失败，请手动复制')
    }
  }

  const handlePolish = async () => {
    setPolishLoading(true)
    try {
      const result = await onPolish(editedText)
      setEditedText(result)
      message.success('AI润色完成')
    } catch {
      message.error('AI润色失败，请检查后端服务')
    } finally {
      setPolishLoading(false)
    }
  }

  const handleReview = async () => {
    setReviewLoading(true)
    try {
      const result = await onReview(editedText)
      setReviewResult(result)
    } catch {
      message.error('AI审查失败，请检查后端服务')
    } finally {
      setReviewLoading(false)
    }
  }

  const handleFill = async () => {
    setFillLoading(true)
    try {
      const result = await onFill(editedText)
      setEditedText(result)
      message.success('AI补齐完成')
    } catch {
      message.error('AI补齐失败，请检查后端服务')
    } finally {
      setFillLoading(false)
    }
  }

  const handleProofread = async () => {
    setProofreadLoading(true)
    try {
      const result = await onProofread(editedText)
      setReviewResult(result)
    } catch {
      message.error('AI校对失败，请检查后端服务')
    } finally {
      setProofreadLoading(false)
    }
  }

  const anyAiLoading = polishLoading || reviewLoading || fillLoading || proofreadLoading

  return (
    <Modal
      title="选区处理"
      open={open}
      onCancel={onClose}
      width={680}
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={onClose}>关闭</Button>
        </div>
      }
    >
      {/* 原文展示 */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <Text strong style={{ fontSize: 13 }}>原文（只读）</Text>
          <Tag style={{ fontSize: 11 }}>
            {selectedText.length}/{maxLength} 字
          </Tag>
          {cellInfo && (
            <Tag color="blue" style={{ fontSize: 11 }}>
              {cellInfo.colKey} · 第{cellInfo.rowIndex + 1}行
            </Tag>
          )}
        </div>
        <div
          style={{
            background: '#f5f7fa',
            border: '1px solid #e8e8e8',
            borderRadius: 4,
            padding: '8px 12px',
            maxHeight: 120,
            overflow: 'auto',
            fontSize: 13,
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            color: '#555',
          }}
        >
          {selectedText || '(无选区内容)'}
        </div>
      </div>

      {/* 编辑区 */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <Text strong style={{ fontSize: 13 }}>编辑后文字</Text>
          <Text style={{ fontSize: 11, color: charCountColor }}>
            {editedText.length}/{maxLength} 字{isOverLimit ? ' (超限，发送时将截断)' : ''}
          </Text>
        </div>
        <TextArea
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          rows={5}
          style={{ fontSize: 13 }}
          placeholder="可在此修改选中的文字..."
        />
      </div>

      {/* 操作按钮 */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: reviewResult ? 12 : 0 }}>
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSendToChat}
          disabled={!editedText.trim()}
        >
          发送给AI对话
        </Button>
        <Button
          icon={<EditOutlined />}
          onClick={handleReplaceCell}
          disabled={!editedText.trim() || !cellInfo}
        >
          替换原文
        </Button>
        <Button
          icon={<CopyOutlined />}
          onClick={handleCopy}
          disabled={!editedText.trim()}
        >
          复制
        </Button>
        <Button
          icon={<BulbOutlined />}
          onClick={handlePolish}
          loading={polishLoading}
          disabled={!editedText.trim() || anyAiLoading}
        >
          AI润色
        </Button>
        <Button
          icon={<FileAddOutlined />}
          onClick={handleFill}
          loading={fillLoading}
          disabled={!editedText.trim() || anyAiLoading}
        >
          AI补齐
        </Button>
        <Button
          icon={<SafetyCertificateOutlined />}
          onClick={handleReview}
          loading={reviewLoading}
          disabled={!editedText.trim() || anyAiLoading}
        >
          AI审查
        </Button>
        <Button
          icon={<CheckCircleOutlined />}
          onClick={handleProofread}
          loading={proofreadLoading}
          disabled={!editedText.trim() || anyAiLoading}
        >
          AI校对
        </Button>
      </div>

      {/* 审查/校对结果 */}
      {(reviewLoading || proofreadLoading) && (
        <div style={{ textAlign: 'center', padding: 12 }}>
          <Spin tip={proofreadLoading ? 'AI校对中...' : 'AI审查中...'} />
        </div>
      )}
      {reviewResult && !reviewLoading && !proofreadLoading && (
        <Collapse
          defaultActiveKey={['review']}
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'review',
              label: 'AI审查结果',
              children: (
                <div
                  style={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: '#333',
                  }}
                >
                  {reviewResult}
                </div>
              ),
            },
          ]}
        />
      )}
    </Modal>
  )
}

export default SelectionDialog
