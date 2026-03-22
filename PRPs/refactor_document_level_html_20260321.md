# PRP: 文档级 HTML 生成 + 语义索引

## 问题/需求

### 背景
- 当前解析结果：每页一个 JSON entry，文档被切碎
- 期望：一个 PDF 一个 HTML + 语义索引 JSON
- 用途：AI 助手上下文注入、前端预览

### 当前问题
1. `content_list_v2.json` 按页组织，不适合检索
2. `generate_complete_html.py` 读取旧版格式
3. 没有语义标签（表格 ID、类型、工序）
4. 样式是绿色主题，需要改为蓝白灰

### 预期结果
```
data/exports_html/
  ├── 全弹设备电缆装配工艺规程/
  │   ├── document.html          # 完整 HTML（蓝白灰主题）
  │   ├── index.json             # 语义索引
  │   └── images/                # 图片资源
  ├── 导弹装配工艺规范/
  │   └── ...
```

---

## 实现方案

### 1. 输入格式（现有）

`content_list_v2.json`:
```json
[
  {
    "type": "table",
    "page_idx": 0,
    "content": {
      "table_caption": [{"content": "G1a"}],
      "html": "<table>...</table>",
      "image_source": {"path": "images/xxx.jpg"}
    }
  },
  ...
]
```

### 2. 输出格式

**document.html**:
- 一个完整的 HTML 文件
- 蓝白灰主题（见下方 CSS）
- 包含所有表格（按页组织，但有语义锚点）
- 快速导航（表格 ID 跳转）

**index.json**:
```json
{
  "name": "全弹设备电缆装配工艺规程",
  "file_name": "全弹设备电缆装配工艺规程.pdf",
  "pages": 44,
  "tables": [
    {
      "id": "G1a",
      "type": "封面",
      "page": 1,
      "summary": "工艺文件封面"
    },
    {
      "id": "G4a",
      "type": "配套表",
      "page": 4,
      "summary": "工艺文件目录、产品工号信息"
    },
    {
      "id": "G18b",
      "type": "配套明细表",
      "page": 10,
      "summary": "装配件配套明细"
    }
  ],
  "processes": ["装前准备", "安装密封圈", "四五舱对接"],
  "materials": ["无水乙醇", "乐泰222", "GD414"],
  "generated_at": "2026-03-21T23:40:00+08:00",
  "html_file": "document.html"
}
```

### 3. 蓝白灰主题 CSS

```css
:root {
  --primary: #2563eb;      /* 蓝色 */
  --primary-dark: #1d4ed8;
  --bg-light: #f8fafc;     /* 浅灰 */
  --bg-white: #ffffff;
  --text-dark: #1e293b;
  --text-gray: #64748b;
  --border: #e2e8f0;
}

body {
  background: var(--bg-light);
  color: var(--text-dark);
}

.page-header {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
}

table {
  border-color: var(--border);
}

th {
  background: var(--bg-light);
}
```

### 4. 实现步骤

1. **更新脚本**
   - 修改 `generate_complete_html.py`
   - 适配 `content_list_v2.json` 格式
   - 提取表格 ID（从 table_caption）
   - 提取工序/材料信息（可从表格内容推断）

2. **生成语义索引**
   - 遍历所有表格
   - 提取 ID、类型、页码
   - 生成 index.json

3. **批量处理**
   - 遍历 `data/exports_vlm_full/` 下所有文档
   - 为每个文档生成 HTML + index.json
   - 输出到 `data/exports_html/`

4. **HTML 结构**
   ```html
   <section id="table-G4a" data-page="4" data-type="配套表">
     <h3>G4a - 配套表</h3>
     <table>...</table>
   </section>
   ```

### 5. 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `scripts/generate_document_html.py` | 新建，替代旧脚本 |
| `scripts/batch_generate_html.py` | 批量处理所有文档 |

---

## 测试验证

### 验证步骤
1. 运行脚本：`python scripts/batch_generate_html.py`
2. 检查输出：`data/exports_html/`
3. 打开 HTML 确认蓝白灰主题
4. 检查 index.json 格式正确

### 成功标准
- [ ] 每个文档一个 HTML 文件
- [ ] 蓝白灰主题正确应用
- [ ] index.json 包含所有表格信息
- [ ] 表格 ID 作为锚点可用
- [ ] 图片路径正确

---

## 项目信息

**项目路径**: `D:\Project Nantianmen\projects\localknowledgebase-word\`
**输入目录**: `data/exports_vlm_full/`
**输出目录**: `data/exports_html/`
**参考文件**: `generate_complete_html.py`
