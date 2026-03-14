# OpenClaw Chrome 扩展操作指南

## 📋 当前状态

✅ **扩展已安装**: `C:\Users\alerl\.openclaw\browser\chrome-extension`  
✅ **Gateway 运行中**: http://127.0.0.1:18789  
✅ **Gateway Token**: `79efeb4c2a2c4e156881d713e73e3eba0fef74b3ac1bb5cd`  
✅ **Chrome 正在运行**

---

## 🔧 第一步：加载 Chrome 扩展

### 1. 打开 Chrome 扩展页面
在 Chrome 地址栏输入：**chrome://extensions**

### 2. 启用开发者模式
- 在页面右上角找到 **"开发者模式"** 开关
- 打开开关

### 3. 加载扩展
1. 点击 **"加载已解压的扩展程序"** 按钮
2. 选择路径：**C:\Users\alerl\.openclaw\browser\chrome-extension**
3. 点击 **"选择文件夹"**

### 4. 固定扩展
1. 在 Chrome 工具栏找到拼图图标 🧩
2. 点击后找到 **"OpenClaw Browser Relay"**
3. 点击图钉图标，将其固定到工具栏

---

## 🔑 第二步：配置扩展 Token

### 1. 打开扩展设置
- 点击工具栏上的 **OpenClaw Browser Relay** 图标
- 点击 **"Settings"** 或 **"配置"**

### 2. 输入 Gateway Token
在 Token 输入框中粘贴：
```
79efeb4c2a2c4e156881d713e73e3eba0fef74b3ac1bb5cd
```

### 3. 保存配置
- 点击 **"Save"** 或 **"保存"**
- 应该看到提示：**Relay reachable and authenticated at http://127.0.0.1:18792/**

---

## 🎯 第三步：使用扩展控制浏览器

### 1. 打开测试页面
在 Chrome 中访问：**http://localhost:3000**

### 2. 附加控制
1. 点击工具栏上的 **OpenClaw Browser Relay** 图标
2. 图标上应该显示 **"ON"**（红色）
3. 表示该标签页已受 OpenClaw 控制

### 3. 测试功能
现在可以回到这里告诉我：
- "查看页面内容"
- "截图页面"
- "点击按钮"
- "测试编辑器功能"

---

## 📸 快速测试命令

完成上述步骤后，可以使用的测试命令：

### 基础测试
```
1. 打开 http://localhost:3000
2. 截图页面，看看是什么样子
3. 查看页面有哪些元素
4. 测试项目选择器功能
```

### 功能测试
```
1. 在编辑器中输入文字
2. 点击工具栏按钮
3. 打开 AI 助手面板
4. 测试保存功能
```

### 样式检查
```
1. 检查按钮是否是蓝色渐变
2. 查看整体配色是否是蓝白灰
3. 截图对比设计稿
```

---

## 🚨 常见问题

### Q1: 扩展图标显示 "!" 或 "..."
**原因**: 中继不可达或认证失败  
**解决**: 
1. 检查 Gateway Token 是否正确
2. 确认 Gateway 正在运行（`openclaw gateway status`）
3. 点击扩展图标重新连接

### Q2: 无法加载扩展
**原因**: 路径不正确或权限问题  
**解决**:
1. 确认路径：`C:\Users\alerl\.openclaw\browser\chrome-extension`
2. 以管理员身份运行 Chrome
3. 检查文件夹是否存在

### Q3: Gateway Token 不匹配
**原因**: 配置文件中的 token 与扩展中的不一致  
**解决**:
1. 使用上面提供的 Token
2. 或访问 http://127.0.0.1:18789/overview 获取新 Token

---

## ✅ 完成检查清单

- [ ] 打开 chrome://extensions
- [ ] 启用开发者模式
- [ ] 加载扩展（选择 chrome-extension 文件夹）
- [ ] 固定扩展到工具栏
- [ ] 点击扩展图标
- [ ] 输入 Gateway Token
- [ ] 保存配置
- [ ] 打开 http://localhost:3000
- [ ] 点击扩展图标附加控制（显示 ON）
- [ ] 回到这里告诉我 "扩展已就绪"

---

**提示**: 完成所有步骤后，我会用 OpenClaw 的 browser 工具自动测试页面功能！
