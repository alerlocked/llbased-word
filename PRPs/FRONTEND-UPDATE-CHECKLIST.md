# 前端组件更新清单

**项目**: 智能工艺文件辅助编辑系统  
**设计版本**: v2.0 (蓝白灰)  
**更新日期**: 2026-03-07

---

## 1. 需要更新的文件

### 1.1 主入口文件
- [ ] `frontend/src/App.tsx` - 应用主题配置
- [ ] `frontend/src/main.tsx` - 导入新样式

### 1.2 样式文件
- [ ] `frontend/src/styles/design-tokens.ts` - 替换为蓝白灰版本
- [ ] `frontend/src/styles/global.css` - 替换为蓝白灰版本

### 1.3 页面组件
- [ ] `frontend/src/pages/WorkspacePage.tsx` - 工作台页面
- [ ] `frontend/src/pages/CreationPage.tsx` - 创作页面
- [ ] `frontend/src/pages/AICreationPage.tsx` - AI 创作页面
- [ ] `frontend/src/pages/KnowledgeBasePage.tsx` - 知识库页面

### 1.4 公共组件
- [ ] `frontend/src/components/common/InlineDiff.tsx` - 差异对比组件
- [ ] `frontend/src/components/common/MarkdownTiptapEditor.tsx` - 编辑器

### 1.5 工作区组件
- [ ] `frontend/src/components/workspace/FloatingToolbar.tsx` - 浮动工具栏
- [ ] `frontend/src/components/workspace/UploadDrawer.tsx` - 上传抽屉
- [ ] `frontend/src/components/workspace/MaterialDrawer.tsx` - 素材抽屉
- [ ] `frontend/src/components/workspace/SettingsDrawer.tsx` - 设置抽屉
- [ ] `frontend/src/components/workspace/PDFViewerDrawer.tsx` - PDF 预览

### 1.6 AI 组件
- [ ] `frontend/src/components/AICreation/AIChatPanel.tsx` - AI 聊天面板
- [ ] `frontend/src/components/AICreation/ImageInsertDialog.tsx` - 图片插入对话框

---

## 2. 更新步骤

### Step 1: 更新设计变量
```bash
# 备份旧文件
cp frontend/src/styles/design-tokens.ts frontend/src/styles/design-tokens-yellow.ts.bak

# 使用新文件
cp frontend/src/styles/design-tokens-blue.ts frontend/src/styles/design-tokens.ts
```

### Step 2: 更新全局样式
```bash
# 备份旧文件
cp frontend/src/styles/global.css frontend/src/styles/global-yellow.css.bak

# 使用新文件
cp frontend/src/styles/global-blue.css frontend/src/styles/global.css
```

### Step 3: 更新导入
```tsx
// frontend/src/main.tsx
import './styles/global-blue.css' // 使用新样式
```

### Step 4: 组件样式检查
- 检查所有使用 `colors.primary` 的地方
- 确认使用新的颜色变量
- 测试 hover、focus、active 状态

---

## 3. 关键更新点

### 3.1 按钮样式
```tsx
// 旧版
<Button style={{ background: '#F5A623' }}>保存</Button>

// 新版
<Button type="primary">保存</Button>
// 自动应用蓝色渐变
```

### 3.2 链接样式
```tsx
// 旧版
<a style={{ color: '#F5A623' }}>链接</a>

// 新版
<a style={{ color: colors.primary }}>链接</a>
// 输出: color: #1890FF
```

### 3.3 卡片阴影
```tsx
// 旧版
<div style={{ boxShadow: shadows.md }}>卡片</div>

// 新版 - 蓝色阴影
<div style={{ boxShadow: shadows.blueGlow }}>高亮卡片</div>
```

### 3.4 边框颜色
```tsx
// 旧版
<div style={{ borderColor: '#E8E8E8' }}>内容</div>

// 新版
<div style={{ borderColor: colors.border }}>内容</div>
// 输出: borderColor: #E2E8F0
```

---

## 4. 测试清单

### 4.1 视觉测试
- [ ] 主按钮颜色是否为蓝色渐变
- [ ] 悬停状态是否有蓝色阴影
- [ ] 输入框聚焦是否有蓝色边框
- [ ] 卡片悬停是否有蓝色边框
- [ ] 文字颜色对比度是否足够
- [ ] 背景色是否协调（白灰蓝）

### 4.2 交互测试
- [ ] 按钮 hover 效果正常
- [ ] 输入框 focus 效果正常
- [ ] 动画流畅（fadeIn, slideUp）
- [ ] 抽屉打开/关闭正常
- [ ] Modal 显示正常

### 4.3 响应式测试
- [ ] 移动端显示正常
- [ ] 平板显示正常
- [ ] 桌面端显示正常

---

## 5. 兼容性考虑

### 5.1 渐变色支持
- 现代浏览器：✅ 完全支持
- IE 11：❌ 不支持渐变（降级为纯色）

### 5.2 Backdrop Filter
- 玻璃卡片效果：需要 backdrop-filter
- 不支持时降级为半透明背景

---

## 6. 性能优化

### 6.1 CSS 变量
- 使用 CSS 变量减少重复
- 动态主题切换更简单

### 6.2 渐变优化
- 渐变角度统一：135deg
- 颜色过渡自然

---

## 7. 设计资源

### 7.1 颜色工具
- Ant Design Color: https://ant.design/docs/spec/colors
- Coolors: https://coolors.co/

### 7.2 设计文件
- Figma: [待补充]
- Sketch: [待补充]

---

**下一步**: 执行更新步骤，逐个检查组件
