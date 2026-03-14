# 前端测试说明

## 测试结构

```
frontend/src/
├── services/__tests__/
│   └── conversationService.test.ts      # TypeScript类型测试
└── components/AICreation/__tests__/
    ├── AIChatPanel.test.tsx             # AIChatPanel事件处理测试
    └── AgentCollaborationView.test.tsx  # AgentCollaborationView组件测试
```

## 运行测试

### 安装依赖

首先需要安装测试框架（如果还没有）：

```bash
cd frontend
npm install --save-dev @testing-library/react @testing-library/jest-dom @types/jest jest jest-environment-jsdom ts-jest
```

### 配置Jest

创建或更新`jest.config.js`：

```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testMatch: ['**/__tests__/**/*.test.{ts,tsx}'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
  ],
};
```

### 运行测试

```bash
# 运行所有测试
npm test

# 运行特定测试文件
npm test -- conversationService.test.ts
npm test -- AIChatPanel.test.tsx
npm test -- AgentCollaborationView.test.tsx

# 运行测试并查看覆盖率
npm test -- --coverage
```

## 测试覆盖范围

### 1. TypeScript类型测试
- ✅ AgentCallEvent类型定义
- ✅ CollaborationEvent类型定义
- ✅ SSEEvent联合类型
- ✅ 所有事件类型的字段验证

### 2. AIChatPanel事件处理测试
- ✅ agent_call事件处理
- ✅ collaboration事件处理
- ✅ 事件类型判断
- ✅ 不同caller和target_agent组合

### 3. AgentCollaborationView组件测试
- ✅ 组件渲染
- ✅ 调用历史显示
- ✅ 调用栈显示
- ✅ 空状态处理

## 注意事项

1. **测试框架**：使用Jest和React Testing Library
2. **Mock依赖**：部分测试需要mock外部依赖（如zustand store）
3. **类型检查**：TypeScript类型测试主要验证类型定义的正确性
4. **组件测试**：组件测试主要验证渲染逻辑和事件处理

## 常见问题

### 1. 模块导入错误
确保`tsconfig.json`中的路径配置正确：
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

### 2. 测试环境配置
确保`setupTests.ts`文件存在并配置了必要的全局设置。

### 3. Mock问题
如果测试失败，检查mock是否正确设置，特别是zustand store的mock。

