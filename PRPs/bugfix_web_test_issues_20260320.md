# PRP: Web测试问题修复

## 问题1：素材库点击行为错误

### 现象
- 点击素材库中的文件 → 添加引用到编辑栏
- 期望：点击文件 → 预览文件内容

### 根因
- `MaterialLibrary.vue` 组件的文件点击事件处理逻辑错误
- 可能是click事件直接调用了"添加引用"函数

### 修复方案
1. 检查 `frontend/src/components/MaterialLibrary.vue`
2. 分离"点击预览"和"添加引用"两个操作：
   - 点击文件名 → 打开预览对话框
   - 双击或点击"添加引用"按钮 → 添加引用到编辑栏
3. 添加文件预览组件（如果不存在）

### 需要修改的文件
- `frontend/src/components/MaterialLibrary.vue`
- `frontend/src/components/FilePreview.vue` (可能需要创建)

---

## 问题2：AI助手无响应

### 现象
- 前端发送 `POST /api/agent/generate-stream`
- 后端接收请求（21:47:07），返回200（0.002秒）
- 没有后续处理日志
- 前端无AI响应

### 根因分析
1. Agent模块可能未正确初始化
2. LLM调用可能超时或失败
3. 流式响应可能未正确建立
4. 知识库检索可能失败

### 修复方案
1. 检查 `backend/app/api/agent.py` 的 `generate_stream` 端点
2. 添加详细日志：
   - Agent初始化状态
   - LLM调用开始/结束
   - 知识库检索过程
   - 流式响应建立
3. 检查知识库配置：
   - 确认"工艺规程"文件夹有内容
   - 确认文件已正确解析
4. 测试LLM连接

### 需要修改的文件
- `backend/app/api/agent.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/rag_service.py` (如果存在)

---

## 测试环境

```yaml
项目路径: D:\Project Nantianmen\projects\localknowledgebase-word
后端: http://127.0.0.1:8000
前端: http://localhost:3000
测试项目ID: 2
测试文件: 全单电缆装配规程.pdf
```

## 验证步骤

### 问题1验证
1. 启动前端
2. 打开素材库
3. 点击文件 → 应该弹出预览对话框
4. 双击或点击"添加引用"按钮 → 应该添加引用到编辑栏

### 问题2验证
1. 打开AI助手
2. 输入："电缆装配具体数据需要量化，修改原工艺方法"
3. 检查后端日志：
   - Agent初始化
   - 知识库检索
   - LLM调用
4. 前端应收到流式响应
