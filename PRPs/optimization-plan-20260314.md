# 工艺文件项目优化计划

> **创建时间**: 2026-03-14
> **状态**: 待执行
> **预计总工期**: 8-12 天

---

## 概述

**跳过任务**: F031 PDM集成、F032 Win7兼容、F033 麒麟兼容

**执行任务**:
1. F034 - WebAssembly PDF 预览
2. F035 - 端到端测试
3. MinerU 版本稳定性
4. PDF 解析功能优化

---

## 任务 1: F034 WebAssembly PDF 预览

### 优先级
🟡 中

### 当前状态
- **状态**: pending
- **现有文件**: `frontend/src/wasm/pdf_viewer.wasm` (201 bytes, 可能是占位文件)
- **PDF组件**: `frontend/src/components/common/PDFViewer/`

### 目标
实现高性能的 WebAssembly PDF 预览组件，支持：
- 快速渲染大型 PDF 文件
- 表格高亮显示
- 文本选择和复制
- 缩放和导航

### 技术方案

#### 方案 A: 使用 pdf.js + WebAssembly (推荐)
```yaml
优势:
  - 成熟稳定
  - 社区支持好
  - 渲染性能优秀
  
实现:
  1. 使用 pdf.js 渲染 PDF
  2. WebAssembly 加速图片处理
  3. Canvas 渲染 + SVG 文本层
```

#### 方案 B: 使用 PDF.js Express
```yaml
优势:
  - 开箱即用
  - 功能丰富
  
劣势:
  - 包体积较大
  - 自定义限制
```

### 子任务

```yaml
piv_001_pdf_preview:
  title: "实现 WebAssembly PDF 预览组件"
  priority: high
  estimated: 3天
  
  tasks:
    - name: "安装 pdf.js 依赖"
      cmd: "cd frontend && npm install pdfjs-dist"
      
    - name: "创建 PDFViewer 组件"
      file: "frontend/src/components/common/PDFViewer/WasmPDFViewer.tsx"
      features:
        - PDF 渲染
        - 缩放控制
        - 页面导航
        - 文本选择
        
    - name: "集成表格高亮"
      features:
        - 从 API 获取表格坐标
        - 高亮显示表格区域
        - 点击跳转到表格详情
        
    - name: "优化性能"
      features:
        - 虚拟滚动（只渲染可见页）
        - 懒加载
        - 缓存机制
        
    - name: "编写单元测试"
      file: "frontend/src/components/common/PDFViewer/__tests__/WasmPDFViewer.test.tsx"
```

### 验收标准
- [ ] PDF 文件可以正确渲染
- [ ] 支持缩放（50% - 300%）
- [ ] 支持页面导航（上一页/下一页/跳转）
- [ ] 表格区域高亮显示
- [ ] 10MB PDF 渲染时间 < 3秒
- [ ] 单元测试覆盖率 >= 70%

### 依赖文件
- `frontend/src/components/common/PDFViewer/PDFTableViewer.tsx`
- `frontend/src/components/common/PDFViewer/ParserConfig.tsx`
- `backend/app/api/document.py` (获取表格坐标)

---

## 任务 2: F035 端到端测试

### 优先级
🟡 中

### 当前状态
- **状态**: partial
- **测试覆盖率**: 30%
- **现有测试**: `backend/tests/`

### 目标
提高测试覆盖率到 80%，建立完整的 E2E 测试体系。

### 子任务

```yaml
piv_002_e2e_tests:
  title: "完善端到端测试"
  priority: high
  estimated: 4天
  
  tasks:
    - name: "补充单元测试"
      targets:
        - "backend/app/agents/functional/" - Agent 测试
        - "backend/app/services/" - 服务测试
        - "backend/app/tools/" - 工具测试
      coverage_target: 80%
      
    - name: "创建 API 集成测试"
      file: "backend/tests/integration/test_api_full.py"
      tests:
        - 文档上传流程
        - PDF 解析流程
        - Agent 对话流程
        - RAG 检索流程
        
    - name: "创建 E2E 测试"
      file: "tests/e2e/test_user_flow.py"
      framework: "Playwright"
      scenarios:
        - 用户登录 → 上传 PDF → 查看解析结果
        - 用户对话 → Agent 响应 → 生成文档
        - 用户搜索 → RAG 检索 → 查看结果
        
    - name: "配置 CI/CD 测试"
      file: ".github/workflows/test.yml"
      features:
        - 自动运行测试
        - 测试覆盖率报告
        - 失败通知
```

### 测试矩阵

| 测试类型 | 工具 | 覆盖率目标 | 文件位置 |
|---------|------|-----------|----------|
| 单元测试 | pytest | 80% | backend/tests/ |
| API测试 | pytest + httpx | 90% | backend/tests/integration/ |
| E2E测试 | Playwright | 核心流程 | tests/e2e/ |
| 前端测试 | Vitest | 70% | frontend/src/**tests**/ |

### 验收标准
- [ ] 后端测试覆盖率 >= 80%
- [ ] API 集成测试通过
- [ ] E2E 测试覆盖核心用户流程
- [ ] CI/CD 自动运行测试
- [ ] 所有测试通过

---

## 任务 3: MinerU 版本稳定性

### 优先级
🔴 高

### 当前状态
- **MinerU 版本**: 2.7.6
- **问题**: API 可能变化，解析效果不稳定
- **配置分散**: 多个文件中都有配置

### 目标
统一 MinerU 配置，验证 API 兼容性，确保解析稳定。

### 子任务

```yaml
piv_003_mineru_stability:
  title: "MinerU 版本稳定性验证"
  priority: critical
  estimated: 2天
  
  tasks:
    - name: "统一配置管理"
      file: "backend/app/config.py"
      changes:
        - 添加 MINERU_* 配置项
        - 集中管理所有 MinerU 参数
        - 支持环境变量覆盖
        
    - name: "API 兼容性测试"
      file: "backend/tests/tools/test_mineru_api.py"
      tests:
        - 测试 vlm-auto-engine 后端
        - 测试 pipeline 后端
        - 测试 hybrid-auto-engine 后端
        - 测试错误处理和回退
        
    - name: "版本锁定"
      file: "backend/requirements.txt"
      changes:
        - 锁定 MinerU 版本: magic-pdf[full]==0.7.6
        - 添加版本检查脚本
        
    - name: "性能基准测试"
      file: "scripts/benchmark_mineru.py"
      metrics:
        - 解析速度（页/秒）
        - 内存使用
        - 准确率对比
```

### 配置集中化

```python
# backend/app/config.py

class MinerUConfig:
    """MinerU 配置集中管理"""
    
    # 版本
    VERSION: str = "0.7.6"
    
    # 后端选择
    BACKEND: str = os.getenv("MINERU_BACKEND", "vlm-auto-engine")
    
    # VLM 配置
    VLM_MODEL: str = os.getenv("MINERU_VLM_MODEL", "default")
    VLM_DEVICE: str = os.getenv("MINERU_VLM_DEVICE", "cuda")
    
    # 解析参数
    PARSE_METHOD: str = "auto"
    TABLE_ENABLE: bool = True
    FORMULA_ENABLE: bool = True
    
    # 输出配置
    OUTPUT_FORMAT: str = "html"
    IMAGE_DPI: int = 200
```

### 验收标准
- [ ] 所有配置集中在 config.py
- [ ] API 兼容性测试通过
- [ ] 版本锁定在 requirements.txt
- [ ] 性能基准测试完成
- [ ] 解析准确率 >= 95%

---

## 任务 4: PDF 解析功能优化

### 优先级
🔴 高

### 当前问题
1. **版本混乱**: 多个 PDF 解析文件
2. **HTML 生成逻辑过时**: generate_complete_html.py 独立在外
3. **解析效果不如 2 月底**

### 目标
统一 PDF 处理流程，优化解析效果，集成 HTML 生成。

### 子任务

```yaml
piv_004_pdf_parsing:
  title: "PDF 解析功能优化"
  priority: critical
  estimated: 3天
  
  tasks:
    - name: "统一处理脚本"
      file: "scripts/pdf_to_html_unified.py"
      features:
        - 单一入口点
        - 支持多种后端（MinerU, pdfplumber）
        - 自动选择最佳后端
        - 统一输出格式
        
    - name: "集成 HTML 生成"
      changes:
        - 合并 generate_complete_html.py 到主流程
        - 支持单页 HTML 和完整 HTML
        - 保留表格结构、文本、图片
        
    - name: "优化表格提取"
      file: "backend/app/tools/table_extractors/mineru_extractor.py"
      improvements:
        - 提高表格识别准确率
        - 支持复杂表格（合并单元格）
        - 支持嵌套表格
        
    - name: "添加图片处理"
      features:
        - 图片自动裁剪
        - 图片质量优化
        - 图片位置保留
        
    - name: "对比测试"
      file: "tests/tools/test_pdf_comparison.py"
      compare:
        - 当前版本 vs 2 月底版本
        - 表格准确率
        - 文本完整性
        - 图片质量
```

### 统一处理流程

```
PDF 输入
    ↓
格式检测
    ↓
后端选择 ─────┬─→ MinerU VLM (复杂表格)
              ├─→ pdfplumber (简单文本)
              └─→ 混合模式 (自动选择)
    ↓
解析处理
    ├─→ 表格提取
    ├─→ 文本提取
    └─→ 图片提取
    ↓
HTML 生成
    ├─→ 单页 HTML
    └─→ 完整 HTML
    ↓
输出结果
```

### 验收标准
- [ ] 统一处理脚本完成
- [ ] HTML 生成集成到主流程
- [ ] 表格识别准确率 >= 95%
- [ ] 文本完整性 >= 98%
- [ ] 图片质量保持不变
- [ ] 对比测试通过

---

## 执行计划

### 阶段 1: 基础优化 (2天)
1. **piv_003**: MinerU 版本稳定性
   - 统一配置
   - 版本锁定
   - API 测试

2. **piv_004 (部分)**: PDF 解析优化
   - 统一处理脚本
   - 集成 HTML 生成

### 阶段 2: 功能开发 (3天)
3. **piv_001**: WebAssembly PDF 预览
   - 组件开发
   - 性能优化

4. **piv_004 (剩余)**: PDF 解析优化
   - 表格提取优化
   - 对比测试

### 阶段 3: 测试完善 (3天)
5. **piv_002**: 端到端测试
   - 单元测试
   - API 测试
   - E2E 测试
   - CI/CD 配置

---

## 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| MinerU API 变化 | 高 | 版本锁定，充分测试 |
| WebAssembly 性能不足 | 中 | 使用 pdf.js 成熟方案 |
| 测试覆盖不足 | 中 | 优先测试核心流程 |
| 解析效果不稳定 | 高 | 多后端备份，自动回退 |

---

## 成功指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 测试覆盖率 | 30% | 80% |
| PDF 解析准确率 | ~90% | >= 95% |
| PDF 预览加载时间 | N/A | < 3秒 (10MB) |
| E2E 测试场景 | 0 | 5+ |
| CI/CD 自动化 | 无 | 完整 |

---

## 注意事项

### Git 推送规范
**⚠️ 所有任务完成后必须遵守 Git 安全推送规范！**

```yaml
禁止上传:
  - .env / .env.local  # 环境变量
  - *.key / *.pem      # 密钥文件
  - data/exports*/     # 测试数据
  - *.pdf              # PDF 文件
  - node_modules/      # 依赖
```

**推送前检查**:
1. `git status --short` 确认只有代码文件
2. `git diff --cached | grep -iE "api_key|secret|password"` 检查敏感信息
3. 确认 .gitignore 正确配置
4. 使用 Conventional Commits 格式

---

## 参考资料

- [pdf.js 文档](https://mozilla.github.io/pdf.js/)
- [MinerU 文档](https://github.com/opendatalab/MinerU)
- [Playwright 文档](https://playwright.dev/python/)
- [pytest 文档](https://docs.pytest.org/)

---

_计划创建于 2026-03-14，等待 Coder 执行_
