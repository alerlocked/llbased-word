# PRP: 前端 PDF 预览与 UI 优化

## 项目
localknowledgebase-word

## 目标
1. 实现 WebAssembly PDF 预览组件 (F034)
2. 优化前端配色为蓝、白、灰主题
3. 改进 UX 体验

## 技术方案

### 1. PDF 预览组件

```yaml
技术栈:
  - pdfjs-dist: PDF 渲染
  - WebAssembly: 性能优化
  - React: 组件框架

功能:
  - PDF 文件预览
  - 缩放（放大/缩小/适应页面）
  - 旋转
  - 下载
  - 分页导航

文件:
  - frontend/src/components/PDFViewer/WasmPDFViewer.tsx
  - frontend/src/components/PDFViewer/PDFControls.tsx
  - frontend/src/components/PDFViewer/PDFPage.tsx
```

### 2. 配色方案

```yaml
主色调:
  - 主色: #1890ff (蓝色)
  - 辅色: #40a9ff (浅蓝)
  - 背景: #f0f2f5 (浅灰)
  - 白色: #ffffff
  - 文字: #262626 (深灰)

组件配色:
  - 按钮: 主色背景 + 白色文字
  - 卡片: 白色背景 + 灰色边框
  - 表格: 白色背景 + 蓝色表头
  - 链接: 主色
  - 激活状态: 浅蓝背景
```

### 3. UX 优化

```yaml
改进点:
  - 响应式布局
  - 加载状态指示
  - 错误提示
  - 空状态设计
  - 动画过渡
  - 键盘导航
```

## 任务拆分

### piv_001: PDF 预览组件基础
- [ ] 安装 pdfjs-dist
- [ ] 创建 WasmPDFViewer.tsx
- [ ] 实现基础渲染
- [ ] 添加加载状态

### piv_002: PDF 控制功能
- [ ] 缩放功能
- [ ] 旋转功能
- [ ] 分页导航
- [ ] 下载功能

### piv_003: 主题配色
- [ ] 定义 CSS 变量
- [ ] 更新 Tailwind 配置
- [ ] 应用到所有组件

### piv_004: UX 优化
- [ ] 响应式布局
- [ ] 加载动画
- [ ] 错误处理
- [ ] 空状态设计

### piv_005: 集成测试
- [ ] 组件测试
- [ ] 交互测试
- [ ] 视觉回归测试

## 验收标准

```yaml
功能:
  - [ ] PDF 正常预览
  - [ ] 缩放/旋转/下载正常
  - [ ] 分页导航正常

视觉:
  - [ ] 配色统一（蓝、白、灰）
  - [ ] 所有页面应用主题
  - [ ] 响应式正常

性能:
  - [ ] PDF 加载 < 3s
  - [ ] 页面切换流畅

测试:
  - [ ] 单元测试通过
  - [ ] E2E 测试通过
```

## 文件路径

```
frontend/
  ├─ src/
  │   ├─ components/
  │   │   └─ PDFViewer/
  │   │       ├─ WasmPDFViewer.tsx
  │   │       ├─ PDFControls.tsx
  │   │       └─ PDFPage.tsx
  │   ├─ styles/
  │   │   └─ theme.css
  │   └─ pages/
  │       ├─ WorkspacePage.tsx (更新)
  │       └─ CreationPage.tsx (更新)
  └─ tailwind.config.js (更新)
```

## 注意事项

1. pdfjs-dist 需要 worker 文件
2. 跨域 PDF 需要配置
3. 主题配色要一致
4. 保持现有功能不受影响
