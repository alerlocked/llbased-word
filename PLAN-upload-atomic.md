# PLAN: 上传 material 原子化（不留孤儿/垃圾）

> slug: `upload-atomic`。先改主仓，同步 win10。

## Context

上传 PDF 创建 material 流程不原子：`保存文件 → DB material → queue task`，中间任一步失败/中断就留孤儿。实证 material_3：`uploads/3/` 文件 + queue task 都在，但 DB material 404（DELETE 返回"素材不存在"）。与已修的重启孤儿漏洞（commit ed9554f）同源——中断留垃圾。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `backend/app/api/creation.py` `upload_document` (行1235) | 原子化：try-except 包裹「文件保存 / DB material / queue task」，任一失败回滚前面已建的，抛 HTTPException |
| `backend/app/api/creation.py` `batch_upload_materials` (行2126) | 同样原子化（每个文件 try-except 回滚，失败不影响其他文件） |

## 回滚逻辑（原子性保证）

- **DB material 创建失败** → 删已保存的文件
- **queue task 失败 / task_id None（文件已存在已解析）** → 删新建的 DB material + 删文件（task_id None 说明重复，不该新建 material）
- 回滚后抛明确 HTTPException（不静默留孤儿）

## 禁区

- 不改业务逻辑（上传/解析/分类流程不变），只加原子性回滚
- 不改 `pdf_queue_manager`（重启孤儿已修）
- 不改前端

## 验证

- 上传正常 PDF → material + 文件 + queue 都建（功能不回归）
- 模拟 queue 失败 → 确认 DB material + 文件回滚（无孤儿）
- kill 中断上传 → 重启检查 uploads/ 无残留孤儿文件

## 下游

- seal → 改主仓 → 同步 win10（源码 + dist）→ 测试 → 经验回流
