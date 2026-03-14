# Implementation Plan: 工艺文件辅助编辑工具

## Overview
构建一个面向工艺师的工艺文件辅助编辑工具，帮助工艺师将脑海中的工艺方法转化为标准的工艺文件术语。系统作为PDM系统的辅助工具，而非替代品，提供智能化的文档生成和编辑支持。

## Requirements Summary
- **目标用户**: 工艺师（PDM系统用户）
- **核心功能**: 工艺方法→标准工艺文件术语的智能转换
- **架构要求**: 主控Agent + 子Agent/工具模块
- **部署环境**: 内网部署，兼容Windows 7和麒麟系统
- **模型集成**: DeepSeek-R1 (14B/32B), BGE-Embedding, BGE-Rerank本地部署
- **交互策略**: 辅助而非替代PDM系统

## Research Findings

### Best Practices
- **渐进式辅助**: 提供逐步引导而非全自动生成
- **上下文感知**: 基于工艺师当前工作状态提供相关建议
- **术语标准化**: 确保生成内容符合行业标准和企业规范
- **离线优先**: 所有核心功能支持完全离线运行
- **轻量级集成**: 与现有PDM系统无缝集成

### Reference Implementations
- **CAD/CAM辅助系统**: 提供设计建议但不替代设计师决策
- **医疗文档辅助**: 帮助医生快速生成标准化病历
- **法律文档助手**: 辅助律师生成标准化法律文书

### Technology Decisions
- **主控Agent架构**: 使用Orchestrator模式管理子Agent
- **本地模型部署**: 所有AI模型本地部署，确保数据安全
- **跨平台兼容**: Electron + WebAssembly支持多平台
- **模块化设计**: 功能模块可独立开发和测试

## Implementation Tasks

### Phase 1: 架构基础搭建

1. **任务: 创建项目结构和基础配置**
   - Description: 建立符合新架构的项目目录结构
   - Files to modify/create:
     - `backend/app/agents/orchestrator/` - 主控Agent目录
     - `backend/app/agents/sub_agents/` - 子Agent目录
     - `backend/app/tools/` - 工具模块目录
     - `frontend/src/agents/` - 前端Agent交互目录
   - Dependencies: None
   - Estimated effort: 2小时

2. **任务: 实现主控Agent基础框架**
   - Description: 创建Orchestrator主控Agent的基础类和接口
   - Files to modify/create:
     - `backend/app/agents/orchestrator/__init__.py`
     - `backend/app/agents/orchestrator/orchestrator.py`
     - `backend/app/agents/orchestrator/state_machine.py`
     - `backend/app/agents/orchestrator/dialog_manager.py`
   - Dependencies: 任务1
   - Estimated effort: 4小时

3. **任务: 实现会话状态机管理**
   - Description: 实现基于状态机的会话管理，支持工艺文件编辑的不同阶段
   - Files to modify/create:
     - `backend/app/agents/orchestrator/states/` - 状态定义目录
     - `backend/app/agents/orchestrator/states/editing_state.py`
     - `backend/app/agents/orchestrator/states/review_state.py`
     - `backend/app/agents/orchestrator/states/generation_state.py`
   - Dependencies: 任务2
   - Estimated effort: 6小时

4. **任务: 实现意图识别和任务分解模块**
   - Description: 将用户输入的工艺意图分解为具体的子任务
   - Files to modify/create:
     - `backend/app/agents/orchestrator/intent_recognizer.py`
     - `backend/app/agents/orchestrator/task_decomposer.py`
     - `backend/app/agents/orchestrator/intent_templates.json`
   - Dependencies: 任务2
   - Estimated effort: 8小时

### Phase 2: 子Agent和工具模块开发

5. **任务: 实现PDF解析子Agent**
   - Description: 基于PyMuPDF实现工艺文档PDF解析，支持表格元素准确提取
   - Files to modify/create:
     - `backend/app/agents/sub_agents/pdf_parser_agent.py`
     - `backend/app/tools/pdf_parser.py`
     - `backend/app/agents/sub_agents/pdf_parser_config.json`
   - Dependencies: 任务1
   - Estimated effort: 6小时

6. **任务: 实现RAG检索子Agent**
   - Description: 集成本地BGE-Embedding和向量数据库，实现工艺知识检索
   - Files to modify/create:
     - `backend/app/agents/sub_agents/rag_agent.py`
     - `backend/app/tools/vector_store.py`
     - `backend/app/agents/sub_agents/embedding_config.json`
   - Dependencies: 任务1
   - Estimated effort: 8小时

7. **任务: 实现术语对齐子Agent**
   - Description: 将工艺师的自然语言描述转换为标准工艺术语
   - Files to modify/create:
     - `backend/app/agents/sub_agents/terminology_agent.py`
     - `backend/app/tools/terminology_mapper.py`
     - `backend/data/terminology/standard_terms.json`
   - Dependencies: 任务1
   - Estimated effort: 6小时

8. **任务: 实现合规检查子Agent**
   - Description: 检查生成的工艺文件是否符合企业标准和行业规范
   - Files to modify/create:
     - `backend/app/agents/sub_agents/compliance_agent.py`
     - `backend/app/tools/compliance_checker.py`
     - `backend/data/compliance/rules.json`
   - Dependencies: 任务1
   - Estimated effort: 6小时

9. **任务: 实现文档生成子Agent**
   - Description: 根据工艺内容生成标准化的工艺文件
   - Files to modify/create:
     - `backend/app/agents/sub_agents/document_agent.py`
     - `backend/app/tools/document_generator.py`
     - `backend/data/templates/process_templates/`
   - Dependencies: 任务1
   - Estimated effort: 8小时

### Phase 3: 模型集成和本地部署

10. **任务: 集成DeepSeek-R1本地推理**
    - Description: 配置DeepSeek-R1模型的本地部署和推理接口
    - Files to modify/create:
      - `backend/app/models/deepseek_r1.py`
      - `backend/app/models/model_config.json`
      - `scripts/setup_models.sh`
    - Dependencies: 任务1
    - Estimated effort: 8小时

11. **任务: 集成BGE-Embedding和BGE-Rerank**
    - Description: 配置BGE系列模型的本地部署和向量检索
    - Files to modify/create:
      - `backend/app/models/bge_embedding.py`
      - `backend/app/models/bge_rerank.py`
      - `backend/app/models/embedding_config.json`
    - Dependencies: 任务1
    - Estimated effort: 6小时

12. **任务: 实现模型服务抽象层**
    - Description: 创建统一的模型服务接口，支持不同模型的切换
    - Files to modify/create:
      - `backend/app/services/model_service.py`
      - `backend/app/services/model_registry.py`
      - `backend/app/services/model_interface.py`
    - Dependencies: 任务10, 任务11
    - Estimated effort: 4小时

### Phase 4: 前端交互设计

13. **任务: 设计工艺师友好的前端交互**
    - Description: 创建面向工艺师的用户界面，强调辅助而非替代
    - Files to modify/create:
      - `frontend/src/components/assistant/AssistantPanel.tsx`
      - `frontend/src/components/assistant/SuggestionCard.tsx`
      - `frontend/src/components/assistant/TerminalInput.tsx`
      - `frontend/src/components/assistant/ProcessEditor.tsx`
    - Dependencies: None
    - Estimated effort: 12小时

14. **任务: 实现PDM系统集成接口**
    - Description: 提供与现有PDM系统的数据交换接口
    - Files to modify/create:
      - `frontend/src/services/pdm_integration.ts`
      - `backend/app/api/pdm_integration.py`
      - `backend/app/services/pdm_service.py`
    - Dependencies: 任务13
    - Estimated effort: 8小时

15. **任务: 实现WebAssembly本地PDF预览**
    - Description: 使用WebAssembly实现浏览器内PDF预览，支持离线使用
    - Files to modify/create:
      - `frontend/src/wasm/pdf_viewer.wasm`
      - `frontend/src/components/pdf/PDFViewer.tsx`
      - `frontend/src/utils/wasm_loader.ts`
    - Dependencies: 任务13
    - Estimated effort: 10小时

### Phase 5: 跨平台兼容性

16. **任务: 配置Windows 7兼容性**
    - Description: 确保所有组件在Windows 7环境下正常运行
    - Files to modify/create:
      - `environment_win7.yml`
      - `scripts/setup_win7.bat`
      - `backend/app/compatibility/win7_compat.py`
    - Dependencies: 任务1
    - Estimated effort: 6小时

17. **任务: 配置麒麟系统兼容性**
    - Description: 确保所有组件在麒麟操作系统下正常运行
    - Files to modify/create:
      - `environment_kylin.yml`
      - `scripts/setup_kylin.sh`
      - `backend/app/compatibility/kylin_compat.py`
    - Dependencies: 任务1
    - Estimated effort: 6小时

18. **任务: 实现内网部署方案**
    - Description: 创建完整的内网部署脚本和文档
    - Files to modify/create:
      - `deploy/internal_network/`
      - `deploy/internal_network/deploy.sh`
      - `deploy/internal_network/README.md`
      - `docs/internal_deployment_guide.md`
    - Dependencies: 任务16, 任务17
    - Estimated effort: 8小时

### Phase 6: 测试和验证

19. **任务: 创建端到端测试用例**
    - Description: 为每个子Agent和核心功能创建测试用例
    - Files to modify/create:
      - `backend/tests/test_orchestrator.py`
      - `backend/tests/test_sub_agents/`
      - `backend/tests/test_models/`
      - `frontend/tests/test_assistant_components/`
    - Dependencies: All previous tasks
    - Estimated effort: 16小时

20. **任务: 实现自动化验证流程**
    - Description: 创建自动化测试和验证流程，确保97%以上准确性
    - Files to modify/create:
      - `scripts/run_validation.py`
      - `scripts/validation_config.json`
      - `backend/tests/validation/accuracy_tests.py`
    - Dependencies: 任务19
    - Estimated effort: 8小时

## Codebase Integration Points

### Files to Modify
- `backend/main.py` - 更新FastAPI应用以支持新Agent架构
- `backend/app/api/` - 添加新的API路由
- `frontend/src/App.tsx` - 集成新的助理组件
- `CLAUDE.md` - 更新项目架构文档

### New Files to Create
- `backend/app/agents/orchestrator/` - 主控Agent完整实现
- `backend/app/agents/sub_agents/` - 所有子Agent实现
- `backend/app/tools/` - 工具模块
- `frontend/src/components/assistant/` - 助理UI组件
- `PRPs/requests/craft-document-assistant.md` - 本计划文件

### Existing Patterns to Follow
- 现有的ProcessDocumentService模式
- 现有的Agent工具集成方式
- 现有的Archon任务管理集成

## Technical Design

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                         前端层                               │
│         React/Vue + WebAssembly（本地PDF预览）               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      API网关层（FastAPI）                    │
│         路由分发 │ 认证 │ 限流 │ 请求聚合                      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    主控Agent（Orchestrator）                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  职责：                                             │   │
│  │  1. 会话状态机管理（State Machine）                  │   │
│  │  2. 意图识别与任务分解（Intent → Sub-tasks）         │   │
│  │  3. 子Agent调度与结果聚合                            │   │
│  │  4. 异常处理与回退策略                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  核心组件：                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 对话管理器    │  │ 任务规划器    │  │ 上下文压缩器  │      │
│  │ DialogMgr    │  │ TaskPlanner  │  │ ContextMgr   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   工具层      │      │   子Agent层   │      │   记忆层      │
│  (Tools)     │      │  (Sub-Agents)│      │  (Memory)    │
├──────────────┤      ├──────────────┤      ├──────────────┤
│• PDF解析器   │      │• 工艺推理Agent│      │• 短期会话记忆 │
│• 标准库查询  │←────→│• 术语对齐Agent│←────→│• 长期工艺知识 │
│• 计算引擎    │      │• 合规检查Agent│      │• 向量数据库   │
│• PDM接口    │      │• 文档生成Agent│      │• 本地文件缓存 │
└──────────────┘      └──────────────┘      └──────────────┘
        ↑                     ↑                     ↑
        └─────────────────────┼─────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    模型层（本地部署）                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DeepSeek-R1 │  │  BGE-Embedding│ │  BGE-Rerank │         │
│  │  (推理主模型)│  │  (向量化)    │  │  (精排序)   │         │
│  │  14B/32B   │  │  本地部署     │  │  本地部署    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow
1. 用户在前端输入工艺意图
2. API网关接收请求并转发给主控Agent
3. 主控Agent进行意图识别和任务分解
4. 调度相应的子Agent执行具体任务
5. 子Agent调用工具模块和模型服务
6. 结果聚合后返回给前端展示
7. 用户确认后保存到PDM系统

### API Endpoints
- `POST /api/assistant/intent` - 提交工艺意图
- `GET /api/assistant/suggestions` - 获取工艺建议
- `POST /api/assistant/generate` - 生成工艺文档
- `GET /api/assistant/terms` - 获取标准术语
- `POST /api/pdm/export` - 导出到PDM系统

## Dependencies and Libraries

### Python Dependencies
- `pymupdf` - PDF解析
- `sentence-transformers` - BGE模型集成
- `transformers` - DeepSeek模型集成
- `chromadb` - 向量数据库
- `fastapi` - API网关
- `uvicorn` - ASGI服务器

### Frontend Dependencies
- `react` - 前端框架
- `webassembly` - 本地PDF处理
- `axios` - API调用
- `antd` - UI组件库

### System Dependencies
- Python 3.10+
- Node.js 16+
- Redis 5.0+ (可选，用于缓存)

## Testing Strategy

### Unit Tests
- 主控Agent状态机测试
- 子Agent功能测试
- 工具模块单元测试
- 模型服务接口测试

### Integration Tests
- Agent间通信测试
- API端到端测试
- PDM系统集成测试
- 跨平台兼容性测试

### End-to-End Tests
- 完整工艺文档生成流程
- 准确性验证（≥97%）
- 性能测试（响应时间<3秒）
- 并发用户测试

### Edge Cases to Cover
- 网络断开时的离线功能
- 大型PDF文件处理
- 复杂工艺术语映射
- 模型推理失败回退

## Success Criteria
- [ ] 主控Agent成功管理子Agent调度
- [ ] PDF解析准确性≥97%
- [ ] 术语对齐准确性≥95%
- [ ] 支持Windows 7和麒麟系统
- [ ] 所有模型本地部署成功
- [ ] 与PDM系统集成正常
- [ ] 前端交互符合工艺师使用习惯
- [ ] 端到端响应时间<3秒

## Notes and Considerations

### Potential Challenges
- **模型资源消耗**: DeepSeek-32B需要大量内存，可能需要提供14B版本作为备选
- **跨平台兼容性**: Windows 7较老，可能需要特殊处理依赖
- **术语标准化**: 需要建立完整的工艺术语库
- **性能优化**: 大型PDF处理可能需要异步处理

### Future Enhancements
- **语音输入支持**: 允许工艺师通过语音描述工艺
- **移动端适配**: 开发移动版本供现场使用
- **协作功能**: 支持多工艺师协作编辑
- **版本控制**: 集成Git进行工艺文档版本管理

### Risk Mitigation
- **模型降级**: 如果32B模型性能不足，自动切换到14B版本
- **功能降级**: 如果某些功能不可用，提供简化版本
- **数据备份**: 定期备份工艺知识库和用户数据

---
*This plan is ready for execution with `/execute-plan`*