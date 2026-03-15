# 前端开发规范 - UX 交互

## 强制要求：进度反馈

### 📋 核心原则

**所有用户需要等待的操作，必须提供进度反馈。**

---

## 适用场景

### 必须有进度条

| 操作类型 | 示例 | 进度类型 |
|---------|------|---------|
| **文件上传** | PDF/Word 上传 | 百分比进度条 |
| **文件处理** | PDF 解析、OCR | 步骤进度 + 百分比 |
| **AI 生成** | 文章生成、润色 | 步骤进度 |
| **批量操作** | 批量导入、导出 | 百分比 + 剩余数量 |
| **数据处理** | 数据同步、迁移 | 百分比进度条 |
| **模型调用** | LLM 推理 | Loading 动画 + 预估时间 |

### 可选进度反馈

| 操作类型 | 示例 | 反馈方式 |
|---------|------|---------|
| **简单保存** | 表单提交 | Loading 动画 |
| **快速查询** | 搜索 | Loading 动画 |
| **页面加载** | 路由切换 | Skeleton 占位符 |

---

## 实现规范

### 1. 文件上传进度条

```tsx
// ✅ 正确示例
import { Upload, Progress, message } from 'antd'

const [uploadProgress, setUploadProgress] = useState(0)
const [uploading, setUploading] = useState(false)

const uploadProps = {
  name: 'file',
  action: '/api/upload',
  showUploadList: false,
  onChange(info) {
    if (info.file.status === 'uploading') {
      setUploading(true)
      setUploadProgress(info.file.percent || 0)
    }
    if (info.file.status === 'done') {
      setUploading(false)
      message.success('上传成功')
    }
    if (info.file.status === 'error') {
      setUploading(false)
      message.error('上传失败')
    }
  }
}

return (
  <div>
    <Upload {...uploadProps}>
      <Button>上传文件</Button>
    </Upload>
    
    {uploading && (
      <Progress 
        percent={Math.round(uploadProgress)} 
        status="active"
      />
    )}
  </div>
)
```

### 2. 文件处理进度（轮询）

```tsx
// ✅ 正确示例 - PDF 解析进度
const [processProgress, setProcessProgress] = useState({
  status: 'idle', // idle | processing | success | error
  step: '',       // 当前步骤
  progress: 0,    // 0-100
  total: 0,       // 总页数
  current: 0      // 当前页数
})

// 上传后开始轮询
const handleUpload = async (file: File) => {
  // 1. 上传文件
  const formData = new FormData()
  formData.append('file', file)
  
  const uploadRes = await fetch('/api/documents', {
    method: 'POST',
    body: formData
  })
  
  const { document_id } = await uploadRes.json()
  
  // 2. 开始轮询进度
  setProcessProgress({ status: 'processing', step: '初始化', progress: 0, total: 0, current: 0 })
  
  const pollInterval = setInterval(async () => {
    const progressRes = await fetch(`/api/documents/${document_id}/progress`)
    const progress = await progressRes.json()
    
    setProcessProgress({
      status: 'processing',
      step: progress.step,        // "正在渲染PDF"
      progress: progress.percent, // 45
      total: progress.total,      // 44
      current: progress.current   // 20
    })
    
    if (progress.status === 'completed') {
      clearInterval(pollInterval)
      setProcessProgress(prev => ({ ...prev, status: 'success' }))
      message.success('文档处理完成')
    }
    
    if (progress.status === 'error') {
      clearInterval(pollInterval)
      setProcessProgress(prev => ({ ...prev, status: 'error' }))
      message.error('文档处理失败')
    }
  }, 1000) // 每秒轮询
}

// 进度展示
return (
  <div>
    {processProgress.status === 'processing' && (
      <Card>
        <div className="progress-header">
          <Spin />
          <span>{processProgress.step}</span>
        </div>
        
        <Progress 
          percent={processProgress.progress}
          status="active"
        />
        
        {processProgress.total > 0 && (
          <div className="progress-detail">
            正在处理第 {processProgress.current} / {processProgress.total} 页
          </div>
        )}
      </Card>
    )}
  </div>
)
```

### 3. AI 生成步骤进度

```tsx
// ✅ 正确示例 - 多步骤进度
const [aiProgress, setAiProgress] = useState({
  status: 'idle',
  steps: [
    { key: 'analyze', title: '分析文档', status: 'waiting' },
    { key: 'extract', title: '提取要点', status: 'waiting' },
    { key: 'generate', title: '生成内容', status: 'waiting' },
    { key: 'review', title: '润色检查', status: 'waiting' }
  ]
})

const updateStep = (stepKey: string, status: string) => {
  setAiProgress(prev => ({
    ...prev,
    steps: prev.steps.map(step => 
      step.key === stepKey ? { ...step, status } : step
    )
  }))
}

// SSE 或 WebSocket 接收进度
useEffect(() => {
  const eventSource = new EventSource('/api/generate/progress')
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    updateStep(data.step, data.status)
  }
  
  return () => eventSource.close()
}, [])

// 渲染步骤
return (
  <Steps current={currentStep}>
    {aiProgress.steps.map(step => (
      <Step 
        key={step.key}
        title={step.title}
        status={step.status}
        icon={step.status === 'processing' ? <LoadingOutlined /> : undefined}
      />
    ))}
  </Steps>
)
```

---

## 后端支持

### 进度 API 设计

```python
# ✅ 后端必须提供进度查询接口

@router.post("/documents")
async def upload_document(file: UploadFile):
    """上传文档"""
    # 创建任务
    task_id = create_task(file)
    
    return {
        "document_id": task_id,
        "status": "processing"
    }

@router.get("/documents/{document_id}/progress")
async def get_progress(document_id: str):
    """查询处理进度"""
    task = get_task(document_id)
    
    return {
        "status": task.status,       # processing | completed | error
        "step": task.current_step,   # "正在渲染PDF"
        "percent": task.percent,     # 45
        "total": task.total,         # 44
        "current": task.current      # 20
    }
```

### 进度存储

```python
# ✅ 使用 Redis 存储进度
import redis

r = redis.Redis()

def update_progress(task_id: str, step: str, current: int, total: int):
    percent = int((current / total) * 100) if total > 0 else 0
    
    r.hset(f"task:{task_id}", mapping={
        "status": "processing",
        "step": step,
        "current": current,
        "total": total,
        "percent": percent
    })
    r.expire(f"task:{task_id}", 3600)  # 1小时过期
```

---

## 进度展示组件

### 通用进度组件

```tsx
// components/ProcessProgress/index.tsx
interface ProcessProgressProps {
  status: 'idle' | 'processing' | 'success' | 'error'
  step?: string
  percent?: number
  current?: number
  total?: number
  onCancel?: () => void
}

export const ProcessProgress: React.FC<ProcessProgressProps> = ({
  status,
  step,
  percent = 0,
  current = 0,
  total = 0,
  onCancel
}) => {
  if (status === 'idle') return null
  
  return (
    <Card className="process-progress-card">
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 状态图标 */}
        <div className="progress-status">
          {status === 'processing' && <Spin size="large" />}
          {status === 'success' && <CheckCircleOutlined style={{ fontSize: 32, color: '#52c41a' }} />}
          {status === 'error' && <CloseCircleOutlined style={{ fontSize: 32, color: '#ff4d4f' }} />}
          
          <Text strong>{step}</Text>
        </div>
        
        {/* 进度条 */}
        {status === 'processing' && (
          <Progress 
            percent={Math.round(percent)}
            status="active"
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
        )}
        
        {/* 详情 */}
        {total > 0 && status === 'processing' && (
          <Text type="secondary">
            正在处理第 {current} / {total} 项
          </Text>
        )}
        
        {/* 取消按钮 */}
        {status === 'processing' && onCancel && (
          <Button onClick={onCancel} danger>
            取消
          </Button>
        )}
      </Space>
    </Card>
  )
}
```

---

## 检查清单

开发时必须检查：

- [ ] 文件上传有进度条
- [ ] 长时间处理有进度反馈
- [ ] 进度条显示当前步骤
- [ ] 进度条显示百分比
- [ ] 有取消按钮（如可能）
- [ ] 失败时有明确提示
- [ ] 成功时有成功提示
- [ ] 进度更新及时（< 1秒）

---

## 参考

- Ant Design Progress: https://ant.design/components/progress
- Ant Design Steps: https://ant.design/components/steps
- Upload 进度: https://ant.design/components/upload

---

_规范创建时间: 2026-03-15_
_最后更新: 2026-03-15_
