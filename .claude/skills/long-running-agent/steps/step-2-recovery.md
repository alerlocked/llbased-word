# Step 2: 状态恢复

## 恢复流程

```bash
# 确认目录
pwd

# 读取进度
cat .claude/progress/current-state.json

# Git 历史
git log --oneline -10

# 功能列表
cat .claude/progress/feature-list.json
```

## 约束

参考: `.claude/constraints/file-operations.md`
