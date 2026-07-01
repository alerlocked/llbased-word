# 需求对齐卡：修 batch-upload 两 bug（buffer API + material_id 未定义）

## 背景
- kylin VM 冒烟（2026-07-01）复现：`POST /api/creation/projects/{id}/materials/batch-upload` 上传 PDF 失败。STATE.md（kylin-env 06-28）已记此阻断。
- `creation.py` 两边同源（localkb/kylin `diff` 一致），bug 在 localkb 上游也有。

## 目标
- 解决谁的问题：工艺文件麒麟版 VM 部署，PDF 批量上传端到端跑通（迁移入口环节）。
- 成功长什么样：batch-upload 上传 PDF → `uploaded_count>0`、落库到 `documents/{material_id}/`、后端日志无 buffer API / NameError；localkb + kylin 两边都过。

## 边界
- 做：修 `backend/app/api/creation.py` `batch_upload_materials` 的两个 bug（见下）。
- 不做：不改 upload-folder（除非 PlanMode 确认同根因）、不改其他端点、不碰环境层（已按 kylin-env 范本打通）。

## 两个 bug（已定位）

### Bug 1 — buffer API（一行修，确定）
- 位置：`creation.py:2157` `file_hash = calculate_file_hash(file_path)`
- 根因：`calculate_file_hash(file_content: bytes)`（`file_utils.py:13`）接 bytes，传了 Path 对象 → `hashlib.md5(path_obj)` 报 "object supporting the buffer API required"。
- 修法：改用同文件 `calculate_file_hash_from_path(file_path)`（`file_utils.py:26`，接路径）。

### Bug 2 — material_id 未定义（NameError，修法待 PlanMode 定）
- 位置：`creation.py:2198` `output_path = ... / "documents" / str(material_id) / "content.html"`
- 根因：`material_id` 在 `batch_upload_materials` 作用域未定义（参数只有 project_id/files/relative_paths/db）。被 bug1 挡住没执行到，修 bug1 后触发 NameError。
- 语义：localkb 架构"文档按 material_id 组织"（CLAUDE.md:79），用 material_id 是对的，但 batch_upload 没创建 material 记录。
- 修法待定：PlanMode 查 `generate_material_index`（upload-folder 调的）/ material 创建逻辑，确定 batch_upload 该如何拿到 material_id。

## 模糊点
1. **落点项目**：localkb 上游改 + sync kylin（推荐，业务同源既有模式 localkb-kylin-sync）／ 直接 kylin 改 ／ 两边各改。倾向 localkb 上游。
2. **bug2 material_id 修法**：待 PlanMode 查 material 创建链路后定（创建 material 记录拿 id，还是别的）。
3. **upload-folder（STATE.md 记 material_id）是否同根因**：PlanMode 顺带查，同根因则一起修（仍在本 slug 范围）。

## 下游
- → 进 PLAN（同 slug `fix-batch-upload`）
