/**
 * SolutionList - 方案列表组件
 * 展示多个改进方案，支持单选或多选
 */
import React, { useState } from 'react'
import { Button, Space, Typography, message } from 'antd'
import { SolutionCard, ImprovementSolution } from './SolutionCard'
import { colors } from '../../styles/design-tokens'

const { Text } = Typography

interface SolutionListProps {
  solutions: ImprovementSolution[]
  sessionId?: string
  allowMultiple?: boolean  // 是否允许多选
  onSelect?: (selectedIds: string[]) => void  // 选择回调
  onConfirm?: (selectedIds: string[]) => void  // 确认回调
}

export const SolutionList: React.FC<SolutionListProps> = ({
  solutions,
  sessionId,
  allowMultiple = true,
  onSelect,
  onConfirm
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const handleSelect = (solutionId: string) => {
    let newSelectedIds: string[]
    
    if (allowMultiple) {
      // 多选模式：切换选中状态
      if (selectedIds.includes(solutionId)) {
        newSelectedIds = selectedIds.filter(id => id !== solutionId)
      } else {
        newSelectedIds = [...selectedIds, solutionId]
      }
    } else {
      // 单选模式：直接替换
      newSelectedIds = [solutionId]
    }
    
    setSelectedIds(newSelectedIds)
    onSelect?.(newSelectedIds)
  }

  const handleConfirm = async () => {
    if (selectedIds.length === 0) {
      message.warning('请至少选择一个方案')
      return
    }

    if (onConfirm) {
      onConfirm(selectedIds)
      return
    }

    // 如果没有提供onConfirm，调用API
    if (sessionId) {
      try {
        const response = await fetch(`http://localhost:8000/api/agent/select-solution`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            solution_ids: selectedIds
          })
        })

        if (!response.ok) {
          throw new Error('选择方案失败')
        }

        message.success('方案选择成功，继续生成中...')
        // 这里应该触发流式响应，由父组件处理
      } catch (error: any) {
        message.error(`选择方案失败: ${error.message}`)
      }
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Text style={{ fontSize: 16, color: colors.textPrimary }}>
          您倾向哪个方向？或者您有其他想法？（{allowMultiple ? '可多选组合' : '单选'}）
        </Text>
        {selectedIds.length > 0 && (
          <Text style={{ marginLeft: 12, color: colors.textSecondary }}>
            已选择 {selectedIds.length} 个方案
          </Text>
        )}
      </div>

      <div style={{ marginBottom: 16 }}>
        {solutions.map((solution) => (
          <SolutionCard
            key={solution.id}
            solution={solution}
            selected={selectedIds.includes(solution.id)}
            onSelect={() => handleSelect(solution.id)}
          />
        ))}
      </div>

      <div style={{ textAlign: 'right' }}>
        <Space>
          {selectedIds.length > 0 && (
            <Button
              type="primary"
              onClick={handleConfirm}
              size="large"
            >
              确认选择并继续
            </Button>
          )}
        </Space>
      </div>
    </div>
  )
}

