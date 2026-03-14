/**
 * InlineDiff - 内联 Diff 显示组件
 * 类似 Cursor 编辑器的代码差异显示：
 * - 绿色背景：新增内容
 * - 红色删除线 + 淡红背景：删除内容
 */
import { useMemo } from 'react'
import { Button, Space } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

// 简单的 diff 算法：逐行比较
interface DiffLine {
  type: 'unchanged' | 'added' | 'removed'
  content: string
}

/**
 * 简单 diff 算法：逐行比较原文和新文
 */
function computeDiff(original: string, modified: string): DiffLine[] {
  const originalLines = original.split('\n')
  const modifiedLines = modified.split('\n')
  const result: DiffLine[] = []
  
  let i = 0, j = 0
  
  while (i < originalLines.length || j < modifiedLines.length) {
    if (i >= originalLines.length) {
      // 原文已结束，剩余都是新增
      result.push({ type: 'added', content: modifiedLines[j] })
      j++
    } else if (j >= modifiedLines.length) {
      // 新文已结束，剩余都是删除
      result.push({ type: 'removed', content: originalLines[i] })
      i++
    } else if (originalLines[i] === modifiedLines[j]) {
      // 相同行
      result.push({ type: 'unchanged', content: originalLines[i] })
      i++
      j++
    } else {
      // 不同：先显示删除，再显示新增
      // 简单处理：查找下一个匹配点
      let foundInModified = modifiedLines.indexOf(originalLines[i], j)
      let foundInOriginal = originalLines.indexOf(modifiedLines[j], i)
      
      if (foundInModified === -1 && foundInOriginal === -1) {
        // 都找不到，当作替换
        result.push({ type: 'removed', content: originalLines[i] })
        result.push({ type: 'added', content: modifiedLines[j] })
        i++
        j++
      } else if (foundInModified !== -1 && (foundInOriginal === -1 || foundInModified - j <= foundInOriginal - i)) {
        // 原文行在新文后面找到了，中间的新文是新增
        while (j < foundInModified) {
          result.push({ type: 'added', content: modifiedLines[j] })
          j++
        }
      } else {
        // 新文行在原文后面找到了，中间的原文是删除
        while (i < foundInOriginal) {
          result.push({ type: 'removed', content: originalLines[i] })
          i++
        }
      }
    }
  }
  
  return result
}

export interface InlineDiffProps {
  /** 原始内容 */
  original: string
  /** 修改后内容 */
  modified: string
  /** 接受修改 */
  onAccept: () => void
  /** 拒绝修改 */
  onReject: () => void
  /** 是否显示操作按钮 */
  showActions?: boolean
  /** 最大高度 */
  maxHeight?: number | string
}

/**
 * 内联 Diff 显示组件
 */
const InlineDiff: React.FC<InlineDiffProps> = ({
  original,
  modified,
  onAccept,
  onReject,
  showActions = true,
  maxHeight = 400
}) => {
  // 计算 diff
  const diffLines = useMemo(() => computeDiff(original, modified), [original, modified])
  
  // 统计变更
  const stats = useMemo(() => {
    const added = diffLines.filter(l => l.type === 'added').length
    const removed = diffLines.filter(l => l.type === 'removed').length
    return { added, removed }
  }, [diffLines])

  return (
    <div style={{ 
      border: `1px solid ${colors.border}`,
      borderRadius: 8,
      overflow: 'hidden',
      background: colors.bgSecondary
    }}>
      {/* Diff 内容区 */}
      <div style={{
        maxHeight,
        overflow: 'auto',
        fontFamily: '"Noto Serif SC", "Source Han Serif CN", Georgia, serif',
        fontSize: 15,
        lineHeight: 1.8
      }}>
        {diffLines.map((line, idx) => (
          <div
            key={idx}
            style={{
              padding: '2px 12px',
              background: 
                line.type === 'added' ? 'rgba(82, 196, 26, 0.15)' :
                line.type === 'removed' ? 'rgba(255, 77, 79, 0.1)' :
                'transparent',
              borderLeft: 
                line.type === 'added' ? '3px solid #52c41a' :
                line.type === 'removed' ? '3px solid #ff4d4f' :
                '3px solid transparent',
              textDecoration: line.type === 'removed' ? 'line-through' : 'none',
              color: 
                line.type === 'removed' ? '#ff4d4f' :
                line.type === 'added' ? '#389e0d' :
                colors.textPrimary,
              opacity: line.type === 'removed' ? 0.7 : 1,
              minHeight: 28,
              display: 'flex',
              alignItems: 'center'
            }}
          >
            {/* 行标记 */}
            <span style={{ 
              width: 20, 
              flexShrink: 0,
              color: colors.textTertiary,
              fontSize: 12,
              marginRight: 8
            }}>
              {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
            </span>
            {/* 内容 */}
            <span style={{ flex: 1, whiteSpace: 'pre-wrap' }}>
              {line.content || ' '}
            </span>
          </div>
        ))}
      </div>

      {/* 底部操作栏 */}
      {showActions && (
        <div style={{
          padding: '10px 12px',
          borderTop: `1px solid ${colors.borderLight}`,
          background: colors.bgTertiary,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          {/* 变更统计 */}
          <div style={{ fontSize: 12, color: colors.textSecondary }}>
            <span style={{ color: '#52c41a', marginRight: 12 }}>+{stats.added} 新增</span>
            <span style={{ color: '#ff4d4f' }}>-{stats.removed} 删除</span>
          </div>
          
          {/* 操作按钮 */}
          <Space>
            <Button
              size="small"
              icon={<CloseOutlined />}
              onClick={onReject}
              style={{ borderRadius: 16 }}
            >
              拒绝
            </Button>
            <Button
              type="primary"
              size="small"
              icon={<CheckOutlined />}
              onClick={onAccept}
              style={{ 
                background: '#52c41a', 
                borderColor: '#52c41a',
                borderRadius: 16
              }}
            >
              接受
            </Button>
          </Space>
        </div>
      )}
    </div>
  )
}

/**
 * FloatingConfirmBar - 浮动确认栏
 * 用于编辑器底部，显示预览模式的确认/取消按钮
 */
interface FloatingConfirmBarProps {
  onAccept: () => void
  onReject: () => void
  stats?: { added: number; removed: number }
}

export const FloatingConfirmBar: React.FC<FloatingConfirmBarProps> = ({
  onAccept,
  onReject,
  stats
}) => {
  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 1000,
      background: colors.textPrimary,
      padding: '12px 24px',
      borderRadius: 24,
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      animation: 'slideUp 0.3s ease-out'
    }}>
      {/* 变更统计 */}
      {stats && (
        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)' }}>
          <span style={{ color: '#52c41a', marginRight: 8 }}>+{stats.added}</span>
          <span style={{ color: '#ff4d4f' }}>-{stats.removed}</span>
        </div>
      )}
      
      <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.2)' }} />
      
      {/* 操作按钮 */}
      <Space>
        <Button
          icon={<CloseOutlined />}
          onClick={onReject}
          style={{ 
            borderRadius: 16,
            color: '#fff',
            borderColor: 'rgba(255,255,255,0.3)',
            background: 'transparent'
          }}
        >
          拒绝
        </Button>
        <Button
          type="primary"
          icon={<CheckOutlined />}
          onClick={onAccept}
          style={{ 
            background: '#52c41a', 
            borderColor: '#52c41a',
            borderRadius: 16
          }}
        >
          接受修改
        </Button>
      </Space>
      
      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateX(-50%) translateY(20px); }
          to { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>
    </div>
  )
}

export default InlineDiff
