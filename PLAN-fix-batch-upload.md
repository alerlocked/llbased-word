# PLAN: 修 batch-upload / upload-folder 三 bug（buffer API + material_id 未定义）

## Context
kylin VM 冒烟（2026-07-01）发现工艺文件麒麟版 PDF 批量上传端到端断（kylin-env STATE.md 06-28 已记阻断）。根因是 `backend/app/api/creation.py` 三个 bug，localkb/kylin 同源（`diff` 一致）。落 localkb 上游修 + sync kylin（既有同源维护模式 localkb-kylin-sync）。

## 改动清单

| 文件:行 | bug | 改什么 |
|---------|-----|--------|
| `backend/app/api/creation.py:2157` | bug1 buffer API | `calculate_file_hash(file_path)` → `calculate_file_hash_from_path(file_path)`（复用 `file_utils.py:26`，接路径） |
| `backend/app/api/creation.py:2186-2214` | bug2 batch_upload material_id | 循环内为每个 PDF 创建 `Material(material_type="document", name=pdf["name"])` + `db.add/commit/refresh` + 关联 `project.material_ids` + 用 `material.id` 替换未定义的 `material_id`（照搬 1280-1290 `upload_document` 模式） |
| `backend/app/api/creation.py:1965-1977` | bug3 generate_material_index material_id | 同 bug2 修法（作用域 project@1887 / db / Material@1919 已有，函数内 1919-1928 已有创建 Material 先例） |

## 禁区
- 不碰 `file_utils.py`（`calculate_file_hash_from_path` 已存在，复用）
- 不碰 Material 模型、其他端点、前端、环境层（已按 kylin-env 范本打通）
- 不改 `upload_document`（正确范例，只照搬其模式）
- sync kylin 时保留 kylin 部署适配层（main.py CORS/reload、.env、nginx、deploy/kylin）

## 验证
1. **localkb 本地**：起后端 → `curl -F files=@test.pdf -F 'relative_paths=["x.pdf"]' POST /api/creation/projects/{id}/materials/batch-upload`（+ upload-folder 同测）→ `uploaded_count>0`、无 buffer API / NameError、`data/documents/{material_id}/content.html` 路径就绪、`project.material_ids` 含新 id
2. **sync kylin + VM 端到端**：覆盖 `backend/app/`（保留 kylin main.py/.env/nginx）→ VM 起服务 → batch-upload 上传 `全单电缆装配规程.pdf` → 落库 + 云端 qwen-vl-max 解析链路跑通（kylin-env PLAN 节点4 验证标准）
3. 测试 PDF 用现有 `data/process_docs/全单电缆装配规程.pdf`；运行产物（日志/截图）进 `.test-runs/fix-batch-upload/`（不进 git）

## 执行顺序
1. localkb 改 creation.py 三处 → 本地冒烟（bug1+2+3 不再报错，上传成功）
2. commit localkb（feat: fix batch-upload/upload-folder material_id + buffer API）
3. sync 到 kylin（覆盖 app/）→ VM 部署 → 端到端冒烟
4. 经验回流（material_id 创建模式 + 范本 NAT 网段适配 → wiki）
