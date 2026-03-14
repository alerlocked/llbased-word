# Step 6: 验证阶段

## 前置条件

所有任务处于 "review" 状态

## 操作

使用 `validator` agent:
1. 启动 validator
2. 提供实现描述
3. 运行测试
4. 报告结果

## 验证策略

参考: `.claude/constraints/validation.md`

```
禁止: 未定位就重新生成整个文件
策略: 只修改错误部分
```
