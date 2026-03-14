# Token 优化指南

> 目的：最大化上下文利用率

## 延迟加载原则

```markdown
<!-- 错误：一次性加载所有内容 -->
Execute Development Plan
Step 1: Read and Parse the Plan (500字详细说明)
Step 2: Project Setup in Archon (500字详细说明)
...（全文3000字，每次加载）

<!-- 正确：索引 + 延迟加载 -->
Execute Development Plan
快速参考: .claude/skills/execute-plan/index.md
当前步骤: {{current_step}}
详细指令: .claude/skills/execute-plan/steps/{{current_step}}.md
```

## 结构优化

### 长文档处理

```
原始文件 (3000字)
    ↓
拆分为
    ├── index.md (200字索引)
    └── steps/
        ├── step-1.md (500字)
        ├── step-2.md (500字)
        └── ...
```

### 按需加载触发条件

| 条件 | 动作 |
|------|------|
| 命令调用时 | 只加载索引 |
| 执行特定步骤时 | 加载对应 step 文件 |
| 遇到错误时 | 加载 error-handling.md |

## 上下文压缩策略

1. **摘要优先**: 先输出摘要，详细内容按需展开
2. **引用代替复制**: 使用文件路径引用，不复制内容
3. **状态快照**: 保存当前状态，避免重复计算
4. **增量更新**: 只传输变更部分

## 文件组织规范

```
.claude/
├── CLAUDE.md           # < 500字 项目索引
├── skills/
│   └── execute-plan/
│       ├── index.md    # < 300字 步骤索引
│       └── steps/      # 按需加载
└── progress/
    └── current-state.json  # 状态快照
```
