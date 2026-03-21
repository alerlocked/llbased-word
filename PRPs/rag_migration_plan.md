# 工艺文件项目 RAG 迁移计划

## 迁移目标

**从**: 传统 RAG（向量检索 + 截断上下文）  
**到**: 文件系统 + 知识图谱（完整上下文 + 结构化记忆）

---

## 已安装 Skills

| Skill | 版本 | 功能 | 状态 |
|-------|------|------|------|
| **self-improving-agent** | 3.0.5 | 自进化学习 | ✅ 已安装 |
| **summarize** | latest | 文件摘要 | ✅ 已安装 |
| **ontology** | latest | 知识图谱 | ✅ 已安装 |
| **file-context-manager** | 1.0.0 | 上下文管理器 | ✅ 已创建 |

---

## 架构变更

### 删除文件

```yaml
backend/app/services/rag_service.py:
  状态: 禁用
  替代: file_context_selector.py
  
backend/app/services/vector_store.py:
  状态: 删除
  替代: file_indexer.py
```

### 新增文件

```yaml
backend/app/services/:
  - file_context_selector.py  # 文件选择器
  - context_injector.py       # 上下文注入器
  - file_indexer.py           # 文件索引器

backend/app/agents/functional/:
  - 更新 writing_agent.py     # 使用新上下文系统
```

---

## 配置变更

### .env

```bash
# 旧配置（禁用）
ENABLE_RAG=false
RAG_MODEL=
RAG_VECTOR_DB=

# 新配置
ENABLE_FILE_CONTEXT=true
CONTEXT_BUDGET=100000
SUMMARIZE_MODEL=google/gemini-3-flash-preview
```

---

## 迁移步骤

### Phase 1: 禁用 RAG（0.5 天）

- [x] 禁用 rag_service.py
- [ ] 移除 RAG 相关导入
- [ ] 更新配置文件

### Phase 2: 实现文件索引器（1 天）

- [ ] 实现 file_indexer.py
- [ ] 扫描素材库
- [ ] 生成 file_index.json
- [ ] 添加关键词提取

### Phase 3: 实现上下文选择器（1.5 天）

- [ ] 实现 file_context_selector.py
- [ ] 相关性计算算法
- [ ] Token 预算管理
- [ ] 集成 ontology 查询

### Phase 4: 实现上下文注入器（1 天）

- [ ] 实现 context_injector.py
- [ ] 分层注入逻辑
- [ ] 集成 summarize CLI
- [ ] 集成 ontology 读取

### Phase 5: 集成和测试（1 天）

- [ ] 更新 writing_agent.py
- [ ] 测试上下文选择
- [ ] 测试 Token 预算
- [ ] 对比 RAG 效果

---

## 预期效果

### 性能提升

| 指标 | 当前（RAG） | 目标（文件系统） |
|------|------------|----------------|
| **上下文完整性** | 70% | 100% |
| **检索精度** | 75% | 95% |
| **生成质量** | 中 | 高 |
| **维护成本** | 高 | 低 |

### 成本变化

```yaml
Token 成本:
  - 上下文长度: 4-8k → 100-200k
  - 单次调用成本: +3-5x
  
维护成本:
  - 向量索引维护: 高 → 零
  - 索引更新时间: 分钟级 → 实时
  - 存储空间: GB 级 → MB 级
```

---

## 风险和缓解

### 风险 1: Token 成本上升

**缓解**:
- 使用 Gemini Flash（低成本长上下文）
- 优化文件选择算法（减少不必要文件）
- 缓存常见上下文

### 风险 2: 文件过多时选择不准

**缓解**:
- 增强关键词提取
- 使用 ontology 关系辅助
- 用户反馈优化

### 风险 3: summarize CLI 依赖

**缓解**:
- 添加 fallback 机制
- 支持多种摘要模型
- 本地缓存摘要结果

---

## 启动迁移

**现在启动 Coder 执行 Phase 1-2？**

任务内容:
1. 禁用 RAG 服务
2. 实现文件索引器
3. 测试索引生成

预计时间: 1.5 天
