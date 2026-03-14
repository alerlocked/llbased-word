---
description: Prime Context for the AI Coding Assistant
argument-hint: [optional: specific-area]
---

# Prime Context (优化版)

## 前置验证步骤

### 0. 环境验证 (必须)

**规则**: 每个项目必须使用独立的 conda 环境，禁止使用 base 或 system 环境

```bash
# 检查当前环境
conda info --envs | grep "*"

# 如果当前是 base 或 system，必须切换到项目环境
# 本项目环境名: gaokao
```

**环境要求**:
- 环境名: `gywj`
- Python: 3.11+
- 依赖: `backend/requirements.txt`

**如果环境不存在，创建命令**:
```bash
conda create -n gywj python=3.10 -y
conda activate gywj
cd backend && pip install -r requirements.txt
```

### 1. 检查当前开发进程

```bash
# 读取当前状态
cat .claude/progress/current-state.json 2>/dev/null || echo "无进行中的任务"
```

### 2. 状态恢复

如果存在进行中的任务：
1. 读取 `.claude/progress/current-state.json`
2. 读取 `.claude/progress/feature-list.json`
3. 查看 Git 历史: `git log --oneline -10`
4. 恢复到上次进度

## 核心初始化

### 步骤1: 读取项目索引
```
读取 CLAUDE.md（项目上下文索引）
```

### 步骤2: 读取项目说明
```
读取 README.md
```

### 步骤3: 精准读取关键文件

**约束**: 参考 `.claude/constraints/file-operations.md`
- 禁止: `glob **`
- 必须: 先 grep 定位，再 read 具体文件


## 输出报告

向用户报告:
- 项目结构
- 项目目的和目标
- 关键文件及其用途
- 重要依赖
- 重要配置文件
- **当前开发进度**（如有）

## 进程保存方案

每次会话结束时，更新:
```json
// .claude/progress/current-state.json
{
  "session_id": "timestamp",
  "current_task": "任务描述",
  "completed_steps": ["step1", "step2"],
  "next_step": "step3",
  "files_modified": ["file1.ts", "file2.ts"],
  "updated_at": "ISO timestamp"
}
```

## 延迟加载

详细约束和步骤按需加载:
- 文件操作约束: `.claude/constraints/file-operations.md`
- 验证策略: `.claude/constraints/validation.md`
- Token优化: `.claude/constraints/token-optimization.md`
