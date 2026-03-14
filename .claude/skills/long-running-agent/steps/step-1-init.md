# Step 1: 初始化/恢复状态

## 检查

```bash
if [ -f .claude/progress/current-state.json ]; then
    echo "恢复现有工作"
else
    echo "开始新任务"
fi
```

## 新任务初始化

- 创建 feature_list.json
- 设置进度文件
- 创建 Archon 任务
