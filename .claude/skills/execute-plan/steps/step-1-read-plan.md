# Step 1: 读取解析计划

## 操作

读取计划文件: `$ARGUMENTS`

## 计划文件内容

- 任务列表
- 代码库组件引用
- 实现上下文

## 约束

参考: `.claude/constraints/file-operations.md`

```
禁止: glob ** 或 glob **/*.ts
必须: 先 grep 定位，再 read 具体文件
限制: 单次对话最多读取 10 个文件
```
