import { useEffect, useRef } from 'react'
import { Button, Space } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { DiffMatchPatch } from 'diff-match-patch'
import { useTheme } from '../../contexts/ThemeContext'

/**
 * 差异高亮组件
 * 使用diff-match-patch计算差异,显示新增(绿色)和删除(红色)内容
 * 提供接受和撤销按钮
 */

interface DiffHighlightProps {
  oldContent: string
  newContent: string
  onAccept?: () => void
  onReject?: () => void
}

const DiffHighlight: React.FC<DiffHighlightProps> = ({ 
  oldContent, 
  newContent, 
  onAccept, 
  onReject 
}) => {
  const { colors } = useTheme()
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // 创建diff-match-patch实例
    const dmp = new DiffMatchPatch()
    
    // 计算差异
    const diffs = dmp.diff_main(oldContent, newContent)
    dmp.diff_cleanupSemantic(diffs)
    
    // 清空容器
    containerRef.current.innerHTML = ''
    
    // 渲染差异
    diffs.forEach(([operation, text]) => {
      const span = document.createElement('span')
      
      if (operation === 1) {
        // 新增内容 - 绿色半透明背景
        span.style.backgroundColor = 'rgba(34, 197, 94, 0.2)'
        span.style.padding = '2px 4px'
        span.style.borderRadius = '2px'
        span.textContent = text
      } else if (operation === -1) {
        // 删除内容 - 红色半透明背景 + 删除线
        span.style.backgroundColor = 'rgba(239, 68, 68, 0.2)'
        span.style.textDecoration = 'line-through'
        span.style.padding = '2px 4px'
        span.style.borderRadius = '2px'
        span.textContent = text
      } else {
        // 未变化内容
        span.textContent = text
      }
      
      containerRef.current?.appendChild(span)
    })
  }, [oldContent, newContent])

  return (
    <div style={{
      backgroundColor: colors.bgSecondary,
      border: `1px solid ${colors.borderColor}`,
      borderRadius: 8,
      padding: 16
    }}>
      {/* 操作按钮 */}
      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        marginBottom: 12
      }}>
        <Space>
          <Button
            type="primary"
            icon={<CheckOutlined />}
            onClick={onAccept}
          >
            接受修改
          </Button>
          <Button
            danger
            icon={<CloseOutlined />}
            onClick={onReject}
          >
            撤销
          </Button>
        </Space>
      </div>

      {/* 差异内容 */}
      <div
        ref={containerRef}
        style={{
          lineHeight: 1.8,
          fontSize: 16,
          padding: 16,
          minHeight: 200,
          backgroundColor: colors.bgPrimary,
          borderRadius: 4,
          color: colors.textPrimary,
          maxHeight: 500,
          overflowY: 'auto'
        }}
      />

      {/* 图例 */}
      <div style={{
        marginTop: 12,
        fontSize: 12,
        color: colors.textSecondary,
        display: 'flex',
        gap: 16
      }}>
        <span>
          <span style={{
            backgroundColor: 'rgba(34, 197, 94, 0.2)',
            padding: '2px 6px',
            borderRadius: 2
          }}>
            新增内容
          </span>
        </span>
        <span>
          <span style={{
            backgroundColor: 'rgba(239, 68, 68, 0.2)',
            padding: '2px 6px',
            borderRadius: 2,
            textDecoration: 'line-through'
          }}>
            删除内容
          </span>
        </span>
      </div>
    </div>
  )
}

export default DiffHighlight

