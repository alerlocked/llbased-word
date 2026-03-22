# PRP: 修复问答模式触发预览问题

## 问题描述

**问题**：问答模式（qa）的回复不应该触发编辑器预览，但当前所有回复都触发了预览

**现象**：
- 用户问"装配工艺卡片有多少页"
- 后端正确返回 `mode: "qa"`
- 前端仍然显示"正在预览 AI 生成内容"

## 根本原因分析

**问题代码位置**：`frontend/src/components/AICreation/AIChatPanel.tsx`

**原因**：React 状态异步更新问题

```typescript
// 第 54 行：currentMode 使用 useState，初始值为 'write'
const [currentMode, setCurrentMode] = useState<'qa' | 'write'>('write')

// 第 270-273 行：SSE 流中接收 mode 消息并更新状态
if (data.type === 'mode') {
  setCurrentMode(data.mode)
  logger.info(`[AI助手] 模式: ${data.mode}`)
}

// 第 393-397 行：预览触发检查
// 生成完成后，根据模式决定是否触发预览
if (contentAccumulator && onPreviewContent && currentMode === 'write') {
  onPreviewContent(contentAccumulator)
  message.success('生成完成，请在编辑器中预览并确认')
}
```

**问题流程**：
1. SSE 流开始接收数据
2. 收到 `mode: "qa"` 消息，调用 `setCurrentMode('qa')`
3. React 状态更新被调度（异步，尚未应用）
4. 流继续处理，收到 `result` 消息
5. 执行预览检查 `currentMode === 'write'`
6. **此时 `currentMode` 仍为初始值 `'write'`**（状态更新尚未完成）
7. 条件为 true，触发 `onPreviewContent()`
8. 用户看到"正在预览 AI 生成内容"

**技术细节**：
- React 的 `useState` 更新是异步的
- 在同一个事件循环中，状态更新不会立即反映
- 即使 `setCurrentMode('qa')` 先执行，检查时 `currentMode` 仍是旧值

## 修复方案

### 方案 A：使用 useRef 替代 useState（推荐）

**优点**：
- 同步更新，立即生效
- 不触发重渲染
- 语义清晰

**修改内容**：

```typescript
// 修改 1：将 useState 改为 useRef
// 原来：
const [currentMode, setCurrentMode] = useState<'qa' | 'write'>('write')

// 修改为：
const currentModeRef = useRef<'qa' | 'write'>('write')

// 修改 2：SSE 流中更新 ref
// 原来：
if (data.type === 'mode') {
  setCurrentMode(data.mode)
  logger.info(`[AI助手] 模式: ${data.mode}`)
}

// 修改为：
if (data.type === 'mode') {
  currentModeRef.current = data.mode
  logger.info(`[AI助手] 模式: ${data.mode}`)
}

// 修改 3：预览检查使用 ref.current
// 原来：
if (contentAccumulator && onPreviewContent && currentMode === 'write') {
  onPreviewContent(contentAccumulator)
  message.success('生成完成，请在编辑器中预览并确认')
}

// 修改为：
if (contentAccumulator && onPreviewContent && currentModeRef.current === 'write') {
  onPreviewContent(contentAccumulator)
  message.success('生成完成，请在编辑器中预览并确认')
}
```

### 方案 B：在 SSE 处理中使用局部变量缓存模式

**优点**：不需要改变状态管理方式

**修改内容**：

```typescript
// 在 handleGenerate 函数开头添加局部变量
const handleGenerate = async () => {
  // ... existing code ...
  
  // 添加：用于缓存当前模式的局部变量
  let currentStreamMode: 'qa' | 'write' = 'write'
  
  // ... existing code ...
  
  // 在 SSE 处理中更新局部变量
  if (data.type === 'mode') {
    currentStreamMode = data.mode
    setCurrentMode(data.mode)  // 保留状态更新（用于UI显示，如果有的话）
    logger.info(`[AI助手] 模式: ${data.mode}`)
  }
  
  // ... existing code ...
  
  // 预览检查使用局部变量
  if (contentAccumulator && onPreviewContent && currentStreamMode === 'write') {
    onPreviewContent(contentAccumulator)
    message.success('生成完成，请在编辑器中预览并确认')
  }
}
```

## 推荐方案：方案 A（useRef）

**理由**：
1. 语义更清晰 - ref 专门用于存储不触发重渲染的可变值
2. 修改范围小，只需 3 处改动
3. 不影响其他逻辑

## 需要修改的文件

| 文件 | 修改行 | 修改内容 |
|------|--------|----------|
| `frontend/src/components/AICreation/AIChatPanel.tsx` | 第 54 行 | `useState` → `useRef` |
| `frontend/src/components/AICreation/AIChatPanel.tsx` | 第 272 行 | `setCurrentMode` → `currentModeRef.current =` |
| `frontend/src/components/AICreation/AIChatPanel.tsx` | 第 394 行 | `currentMode` → `currentModeRef.current` |

## 测试验证

### 测试场景 1：问答模式
1. 输入问题："装配工艺卡片有多少页"
2. 后端返回 `mode: "qa"`
3. **预期**：回复直接显示在聊天面板，不触发编辑器预览
4. **当前**：触发了编辑器预览（Bug）

### 测试场景 2：写作模式
1. 输入写作需求："写一份关于人工智能的报告"
2. 后端返回 `mode: "write"`
3. **预期**：生成完成后触发编辑器预览
4. **当前**：正常触发（符合预期）

### 测试场景 3：模式切换
1. 先进行问答操作
2. 再进行写作操作
3. **预期**：每次操作都正确按模式处理

## 项目信息

- **项目**：localknowledgebase-word
- **工作目录**：D:\Project Nantianmen\projects\localknowledgebase-word
- **PRP 创建日期**：2026-03-22
- **优先级**：中
