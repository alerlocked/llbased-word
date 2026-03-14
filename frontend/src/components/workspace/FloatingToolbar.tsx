/**
 * FloatingToolbar - 悬浮快捷编辑面板
 */
import { useEffect, useState, useCallback, useRef } from 'react'
import { Button, Input, Spin, message } from 'antd'
import { SendOutlined, ThunderboltOutlined, PictureOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

const { TextArea } = Input

interface FloatingToolbarProps {
  containerRef: React.RefObject<HTMLTextAreaElement | any>
  onReplaceSelection: (originalText: string, newText: string, start: number, end: number) => void
  projectId: number | null
  onOpenImageDialog?: () => void
}

interface ToolbarPosition {
  top: number
  left: number
  visible: boolean
}

interface SelectionRange {
  start: number
  end: number
  text: string
}

const FloatingToolbar: React.FC<FloatingToolbarProps> = ({
  containerRef,
  onReplaceSelection,
  projectId,
  onOpenImageDialog
}) => {
  const [position, setPosition] = useState<ToolbarPosition>({ top: 0, left: 0, visible: false })
  const [selection, setSelection] = useState<SelectionRange | null>(null)
  const [quickInput, setQuickInput] = useState('')
  const [processing, setProcessing] = useState(false)

  // 处理文本选择
  useEffect(() => {
    const handleMouseUp = () => {
      const selection = window.getSelection()
      if (!selection || selection.isCollapsed) {
        setPosition(prev => ({ ...prev, visible: false }))
        return
      }

      const text = selection.toString().trim()
      if (!text) {
        setPosition(prev => ({ ...prev, visible: false }))
        return
      }

      // 计算位置
      const range = selection.getRangeAt(0)
      const rect = range.getBoundingClientRect()

      setPosition({
        top: rect.top - 50,
        left: rect.left + rect.width / 2 - 100,
        visible: true
      })
      setSelection({ start: 0, end: text.length, text })
    }

    document.addEventListener('mouseup', handleMouseUp)
    return () => document.removeEventListener('mouseup', handleMouseUp)
  }, [])

  // 处理快捷操作
  const handleQuickAction = async (action: string) => {
    if (!selection || !projectId) return

    setProcessing(true)
    try {
      // TODO: 调用 AI API
      message.info(`${action}: ${selection.text.slice(0, 20)}...`)
    } catch (error) {
      message.error('操作失败')
    } finally {
      setProcessing(false)
    }
  }

  if (!position.visible || !selection) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        zIndex: 1000,
        background: colors.bgSecondary,
        borderRadius: 8,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        padding: '8px 12px',
        display: 'flex',
        gap: 8,
        alignItems: 'center'
      }}
    >
      {processing ? (
        <Spin size="small" />
      ) : (
        <>
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={() => handleQuickAction('润色')}
          >
            润色
          </Button>
          <Button
            size="small"
            icon={<PictureOutlined />}
            onClick={onOpenImageDialog}
          >
            插图
          </Button>
        </>
      )}
    </div>
  )
}

export default FloatingToolbar
