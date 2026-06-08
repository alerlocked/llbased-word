/**
 * TodoList - 待办事项列表组件
 * 显示待办事项，支持标记完成，显示完成进度
 */
import React, { useState, useEffect } from 'react'
import { List, Checkbox, Typography, Tag, Progress, message } from 'antd'
import { CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { colors } from '../../styles/design-tokens'

const { Text, Paragraph } = Typography

export interface TodoItem {
  id: string
  title: string
  description?: string
  status: 'pending' | 'completed'
  priority: 'high' | 'medium' | 'low'
  created_at?: string
}

interface TodoListProps {
  todos: TodoItem[]
  sessionId?: string
  onTodoChange?: (todos: TodoItem[]) => void  // 待办变化回调
}

export const TodoList: React.FC<TodoListProps> = ({
  todos,
  sessionId,
  onTodoChange
}) => {
  const [localTodos, setLocalTodos] = useState<TodoItem[]>(todos)

  useEffect(() => {
    setLocalTodos(todos)
  }, [todos])

  const priorityColors: Record<string, string> = {
    high: '#ff4d4f',
    medium: '#faad14',
    low: '#52c41a'
  }

  const priorityText: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }

  const completedCount = localTodos.filter(t => t.status === 'completed').length
  const totalCount = localTodos.length
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  const handleToggleTodo = async (todoId: string) => {
    const todo = localTodos.find(t => t.id === todoId)
    if (!todo) return

    const newStatus = todo.status === 'completed' ? 'pending' as const : 'completed' as const

    // 乐观更新UI
    const updatedTodos: TodoItem[] = localTodos.map(t =>
      t.id === todoId ? { ...t, status: newStatus } : t
    )
    setLocalTodos(updatedTodos)
    onTodoChange?.(updatedTodos)

    // 如果是标记完成，调用API
    if (newStatus === 'completed' && sessionId) {
      try {
        const response = await fetch(
          `http://localhost:8000/api/agent/todos/${sessionId}/${todoId}/complete`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
          }
        )

        if (!response.ok) {
          throw new Error('更新待办状态失败')
        }

        // API调用成功，状态已更新
      } catch (error: any) {
        // 恢复原状态
        const restoredTodos: TodoItem[] = localTodos.map(t =>
          t.id === todoId ? { ...t, status: todo.status } : t
        )
        setLocalTodos(restoredTodos)
        onTodoChange?.(restoredTodos)
        message.error(`更新待办状态失败: ${error.message}`)
      }
    }
  }

  if (localTodos.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '20px', color: colors.textSecondary }}>
        <Text type="secondary">暂无待办事项</Text>
      </div>
    )
  }

  return (
    <div>
      {/* 进度显示 */}
      <div style={{ marginBottom: 16, padding: '12px 16px', background: colors.bgSecondary, borderRadius: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Text strong style={{ fontSize: 14 }}>
            待办事项 {completedCount}/{totalCount}
          </Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>
            {progressPercent}%
          </Text>
        </div>
        <Progress 
          percent={progressPercent} 
          showInfo={false}
          strokeColor={colors.primary}
          size="small"
        />
      </div>

      {/* 待办列表 */}
      <List
        dataSource={localTodos}
        renderItem={(todo) => (
          <List.Item
            style={{
              padding: '12px 16px',
              borderBottom: `1px solid ${colors.borderLight}`,
              background: todo.status === 'completed' ? '#f6ffed' : '#fff',
              opacity: todo.status === 'completed' ? 0.8 : 1
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', width: '100%' }}>
              <Checkbox
                checked={todo.status === 'completed'}
                onChange={() => handleToggleTodo(todo.id)}
                style={{ marginRight: 12, marginTop: 2 }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                  {todo.status === 'completed' ? (
                    <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                  ) : (
                    <ClockCircleOutlined style={{ color: colors.textSecondary, marginRight: 8 }} />
                  )}
                  <Text 
                    strong 
                    style={{ 
                      textDecoration: todo.status === 'completed' ? 'line-through' : 'none',
                      color: todo.status === 'completed' ? colors.textSecondary : colors.textPrimary
                    }}
                  >
                    {todo.title}
                  </Text>
                  <Tag 
                    color={priorityColors[todo.priority]} 
                    style={{ marginLeft: 8 }}
                  >
                    {priorityText[todo.priority]}优先级
                  </Tag>
                </div>
                {todo.description && (
                  <Paragraph 
                    style={{ 
                      margin: 0, 
                      marginLeft: 24,
                      fontSize: 12, 
                      color: colors.textSecondary 
                    }}
                  >
                    {todo.description}
                  </Paragraph>
                )}
              </div>
            </div>
          </List.Item>
        )}
      />
    </div>
  )
}

