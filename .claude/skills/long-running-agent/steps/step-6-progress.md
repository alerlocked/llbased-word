# Step 6: 进度更新

## 本地更新

```bash
# 更新状态文件
# .claude/progress/current-state.json
```

## Archon 更新

```
PATCH /api/tasks/{id}
status: "review"
progress: 100
```

## 上传测试结果

```
POST /api/tasks/{id}/results
type: "test_results"
```
