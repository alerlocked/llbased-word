# 组件测试 Skill

用于测试系统单个组件的功能是否正常。

## 触发条件

用户请求：
- 测试某个组件
- 组件测试
- 运行组件测试
- /component-test

## 测试范围

### 后端组件测试

1. **FastAPI 服务测试**
   ```bash
   # 验证后端服务启动
   curl http://localhost:8000/health
   curl http://localhost:8000/
   ```

2. **数据库连接测试**
   ```bash
   cd backend
   conda activate gywj
   python -c "from app.database import engine; print('DB OK:', engine.url)"
   ```

3. **API 端点测试**
   ```bash
   # 测试项目 API
   curl http://localhost:8000/api/creation/projects

   # 测试工艺文档 API
   curl http://localhost:8000/api/process-documents/
   ```

4. **PDF 解析器测试**
   ```bash
   cd backend
   conda activate gywj
   python -c "from app.tools.pdf_parser import PDFParser; print('PDF Parser OK')"
   ```

5. **Agent 系统测试**
   ```bash
   cd backend
   conda activate gywj
   python -c "from app.agents import registry; print('Agents:', list(registry._workflows.keys()))"
   ```

### 前端组件测试

1. **前端服务测试**
   ```bash
   curl http://localhost:3000
   ```

2. **组件加载检查**
   - 打开浏览器开发者工具 (F12)
   - 检查 Console 是否有错误
   - 检查 Network 标签页是否有失败的请求

3. **状态管理测试**
   - 在浏览器 Console 中执行:
   ```javascript
   // 检查 Zustand store
   console.log('Store:', useCreationStore?.getState?.())
   ```

## 测试流程

1. **环境检查**
   - 确认 conda 环境 `gywj` 已激活
   - 确认 Node.js 已安装
   - 确认后端服务运行在 8000 端口
   - 确认前端服务运行在 3000 端口

2. **运行测试**
   - 根据用户指定的组件类型运行对应测试
   - 记录测试结果

3. **报告结果**
   - 列出通过的测试
   - 列出失败的测试及原因
   - 提供修复建议

## 快速诊断命令

```bash
# 一键诊断后端
cd D:\ai_idea\localknowledgebase-word\backend && conda run -n gywj python -c "
from main import app
print('✅ FastAPI app 加载成功')

from app.database import engine
print('✅ 数据库连接:', engine.url)

from app.tools.pdf_parser import PDFParser
print('✅ PDF解析器可用')

from app.agents import registry
print('✅ Agent注册表:', list(registry._workflows.keys()))
"

# 一键诊断前端
curl -s http://localhost:3000 > /dev/null && echo "✅ 前端服务正常" || echo "❌ 前端服务异常"
```

## 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 后端无法启动 | 依赖缺失 | 运行 `pip install -r requirements.txt` |
| 数据库错误 | SQLite 文件损坏 | 删除 `data/` 目录下的 `.db` 文件重新初始化 |
| 前端空白 | API 连接失败 | 检查后端是否运行，检查 CORS 配置 |
| 组件加载失败 | 模块导入错误 | 检查控制台错误信息 |
