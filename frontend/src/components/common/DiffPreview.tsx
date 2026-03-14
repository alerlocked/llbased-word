/**
 * DiffPreview - 通用 Diff 预览组件
 * 显示原文与修改后的对比，支持接受/拒绝操作
 */
import { useState } from 'react'
import { Button, Space, Spin } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

export type DiffType = 'replace' | 'insert' | 'append'

export interface DiffPreviewProps {
  /** 原文（替换模式时显示） */
  original?: string
  /** 修改后的内容 */
  modified: string
  /** 操作类型 */
  type: DiffType
  /** 是否正在加载 */
  loading?: boolean
  /** 接受修改 */
  onAccept: () => void
  /** 拒绝修改 */
  onReject: () => void
  /** 紧凑模式（用于悬浮面板） */
  compact?: boolean
}

/**
 * Diff 预览组件
 * - replace: 显示删除线原文 + 高亮新文
 * - insert/append: 只显示高亮新文
 */
const DiffPreview: React.FC<DiffPreviewProps> = ({
  original,
  modified,
  type,
  loading = false,
  onAccept,
  onReject,
  compact = false
}) => {
  // 快捷键支持
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onAccept()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onReject()
    }
  }

  if (loading) {
    return (
      <div style={{
        padding: compact ? 12 : 16,
        background: colors.bgTertiary,
        borderRadius: 8,
        textAlign: 'center'
      }}>
        <Spin size="small" />
        <span style={{ marginLeft: 8, color: colors.textSecondary, fontSize: 13 }}>
          AI 处理中...
        </span>
      </div>
    )
  }

  return (
    <div 
      tabIndex={0}
      onKeyDown={handleKeyDown}
      style={{
        background: compact ? 'transparent' : colors.bgSecondary,
        borderRadius: compact ? 0 : 10,
        border: compact ? 'none' : `1px solid ${colors.borderLight}`,
        overflow: 'hidden',
        outline: 'none'
      }}
    >
      {/* Diff 内容区 */}
      <div style={{
        padding: compact ? '8px 0' : 12,
        maxHeight: compact ? 150 : 250,
        overflow: 'auto',
        fontSize: compact ? 13 : 14,
        lineHeight: 1.7
      }}>
        {/* 替换模式：显示原文（删除线）+ 新文（高亮） */}
        {type === 'replace' && original && (
          <>
            {/* 原文 - 红色删除线 */}
            <div style={{
              background: 'rgba(255, 77, 79, 0.1)',
              padding: '6px 10px',
              borderRadius: 6,
              marginBottom: 8,
              borderLeft: '3px solid #ff4d4f'
            }}>
              <span style={{
                textDecoration: 'line-through',
                color: '#ff4d4f',
                opacity: 0.8
              }}>
                {original}
              </span>
            </div>
            
            {/* 新文 - 绿色高亮 */}
            <div style={{
              background: 'rgba(82, 196, 26, 0.1)',
              padding: '6px 10px',
              borderRadius: 6,
              borderLeft: '3px solid #52c41a'
            }}>
              <span style={{ color: '#52c41a' }}>
                {modified}
              </span>
            </div>
          </>
        )}

        {/* 插入/追加模式：只显示新文 */}
        {(type === 'insert' || type === 'append') && (
          <div style={{
            background: colors.primaryLight,
            padding: '6px 10px',
            borderRadius: 6,
            borderLeft: `3px solid ${colors.primary}`
          }}>
            <span style={{ color: colors.textPrimary }}>
              {modified}
            </span>
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div style={{
        padding: compact ? '8px 0 0' : '8px 12px 12px',
        display: 'flex',
        justifyContent: 'flex-end',
        gap: 8,
        borderTop: compact ? 'none' : `1px solid ${colors.borderLight}`
      }}>
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
      </div>

      {/* 快捷键提示 */}
      {!compact && (
        <div style={{
          padding: '0 12px 8px',
          fontSize: 11,
          color: colors.textTertiary,
          textAlign: 'right'
        }}>
          Enter 接受 · Esc 拒绝
        </div>
      )}
    </div>
  )
}

export default DiffPreview
