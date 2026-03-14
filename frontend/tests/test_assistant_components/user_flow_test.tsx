import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AssistantPanel from '../../../src/components/assistant/AssistantPanel';
import SuggestionCard from '../../../src/components/assistant/SuggestionCard';
import TerminalInput from '../../../src/components/assistant/TerminalInput';
import ProcessEditor from '../../../src/components/assistant/ProcessEditor';

// Mock API calls
const mockSendMessage = jest.fn();
const mockSuggestions = [
  {
    id: 'suggestion-1',
    type: 'terminology',
    content: '建议将"车床加工"改为标准术语"车削"',
    confidence: 0.95,
    actions: [
      { label: '应用', action: jest.fn() },
      { label: '忽略', action: jest.fn() }
    ]
  },
  {
    id: 'suggestion-2',
    type: 'compliance',
    content: '缺少安全防护要求，请添加相关说明',
    confidence: 0.85,
    actions: [
      { label: '添加', action: jest.fn() },
      { label: '稍后处理', action: jest.fn() }
    ]
  }
];

const mockProcessDocument = {
  id: 'PROC-2024-001',
  name: '主轴箱加工工艺',
  operations: [
    {
      id: 'op-1',
      sequence: 1,
      name: '车削外圆',
      description: '使用数控车床加工外圆至尺寸要求',
      tools: ['数控车床', '外圆车刀'],
      parameters: {
        cutting_speed: 200,
        feed_rate: 0.2,
        depth_of_cut: 2.0
      }
    }
  ],
  parameters: {
    cutting_speed: 200,
    feed_rate: 0.2
  },
  qualityRequirements: [
    {
      id: 'qr-1',
      description: '外圆尺寸公差±0.02mm',
      standard: 'GB/T 1804-m',
      tolerance: '±0.02mm'
    }
  ]
};

describe('用户使用流程测试', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('用户场景: 工艺师创建新工艺文件', async () => {
    // 渲染助理面板
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={mockSuggestions}
        isLoading={false}
        processDocument={mockProcessDocument}
      />
    );

    // 验证组件渲染
    expect(screen.getByText('工艺文件助理')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('例如：为零件A创建车削工艺...')).toBeInTheDocument();

    // 用户输入工艺需求
    const inputElement = screen.getByPlaceholderText('例如：为零件A创建车削工艺...');
    await userEvent.type(inputElement, '为零件A创建车削工艺');

    // 用户点击发送按钮
    const sendButton = screen.getByText('发送');
    await userEvent.click(sendButton);

    // 验证消息发送
    expect(mockSendMessage).toHaveBeenCalledWith('为零件A创建车削工艺');

    // 验证建议显示
    expect(screen.getByText('建议:')).toBeInTheDocument();
    expect(screen.getByText('建议将"车床加工"改为标准术语"车削"')).toBeInTheDocument();
    expect(screen.getByText('缺少安全防护要求，请添加相关说明')).toBeInTheDocument();

    // 验证工艺编辑器显示
    expect(screen.getByText('工艺文件: 主轴箱加工工艺')).toBeInTheDocument();
    expect(screen.getByText('车削外圆')).toBeInTheDocument();
  });

  test('用户场景: 工艺师与建议卡片交互', async () => {
    render(<SuggestionCard suggestion={mockSuggestions[0]} />);

    // 验证建议卡片渲染
    expect(screen.getByText('术语建议 • 95%')).toBeInTheDocument();
    expect(screen.getByText('建议将"车床加工"改为标准术语"车削"')).toBeInTheDocument();

    // 用户点击应用按钮
    const applyButton = screen.getByText('应用');
    await userEvent.click(applyButton);

    // 验证动作执行
    expect(mockSuggestions[0].actions[0].action).toHaveBeenCalled();
  });

  test('用户场景: 工艺师使用终端输入', async () => {
    const mockOnChange = jest.fn();
    const mockOnSend = jest.fn();

    render(
      <TerminalInput
        value=""
        onChange={mockOnChange}
        onSend={mockOnSend}
        placeholder="输入您的工艺需求..."
      />
    );

    // 用户输入文本
    const textarea = screen.getByRole('textbox');
    await userEvent.type(textarea, '修改工序参数');

    // 验证输入变化
    expect(mockOnChange).toHaveBeenCalledWith('修改工序参数');

    // 用户按Enter发送
    await userEvent.keyboard('{Enter}');

    // 验证发送功能
    expect(mockOnSend).toHaveBeenCalled();
  });

  test('用户场景: 工艺师编辑工艺文件', async () => {
    const mockOnChange = jest.fn();

    render(<ProcessEditor document={mockProcessDocument} onChange={mockOnChange} />);

    // 验证工艺编辑器渲染
    expect(screen.getByText('工艺文件: 主轴箱加工工艺')).toBeInTheDocument();
    expect(screen.getByText('车削外圆')).toBeInTheDocument();

    // 用户点击添加工序按钮
    const addButton = screen.getByText('添加工序');
    await userEvent.click(addButton);

    // 验证模态框显示
    expect(screen.getByText('添加工序')).toBeInTheDocument();

    // 用户填写工序信息
    await userEvent.type(screen.getByLabelText('工序序号'), '2');
    await userEvent.type(screen.getByLabelText('工序名称'), '铣削平面');
    await userEvent.type(screen.getByLabelText('工序描述'), '使用数控铣床加工平面');

    // 用户点击保存
    const saveButton = screen.getByText('保存');
    await userEvent.click(saveButton);

    // 验证文档更新
    expect(mockOnChange).toHaveBeenCalled();
  });

  test('用户场景: 工艺师查看和确认生成的工艺文件', async () => {
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={[]}
        isLoading={false}
        processDocument={mockProcessDocument}
      />
    );

    // 验证生成的工艺文件显示
    expect(screen.getByText('主轴箱加工工艺')).toBeInTheDocument();
    expect(screen.getByText('车削外圆')).toBeInTheDocument();
    expect(screen.getByText('使用数控车床加工外圆至尺寸要求')).toBeInTheDocument();

    // 用户可以查看工序详情
    const editButton = screen.getByText('编辑');
    await userEvent.click(editButton);

    // 验证编辑功能可用
    expect(screen.getByText('编辑工序')).toBeInTheDocument();
  });

  test('用户场景: 工艺师处理加载状态', () => {
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={[]}
        isLoading={true}
        processDocument={null}
      />
    );

    // 验证加载状态显示
    expect(screen.getByText('正在处理您的请求...')).toBeInTheDocument();
  });

  test('用户场景: 工艺师处理错误状态', () => {
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={[]}
        isLoading={false}
        error="网络连接失败"
        processDocument={null}
      />
    );

    // 验证错误状态显示
    expect(screen.getByText('操作失败')).toBeInTheDocument();
    expect(screen.getByText('网络连接失败')).toBeInTheDocument();
  });

  test('用户场景: 工艺师进行多轮对话', async () => {
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={mockSuggestions}
        isLoading={false}
        processDocument={mockProcessDocument}
      />
    );

    // 第一轮: 创建工艺文件
    await userEvent.type(screen.getByPlaceholderText('例如：为零件A创建车削工艺...'), '创建新工艺');
    await userEvent.click(screen.getByText('发送'));

    expect(mockSendMessage).toHaveBeenCalledWith('创建新工艺');

    // 第二轮: 编辑工艺参数
    await userEvent.clear(screen.getByPlaceholderText('例如：为零件A创建车削工艺...'));
    await userEvent.type(screen.getByPlaceholderText('例如：为零件A创建车削工艺...'), '修改切削速度');
    await userEvent.click(screen.getByText('发送'));

    expect(mockSendMessage).toHaveBeenCalledWith('修改切削速度');
  });

  test('用户场景: 工艺师导出到PDM系统', async () => {
    // 这个测试需要集成PDM服务，这里验证UI元素
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={mockSuggestions}
        isLoading={false}
        processDocument={mockProcessDocument}
      />
    );

    // 验证工艺文件显示
    expect(screen.getByText('主轴箱加工工艺')).toBeInTheDocument();

    // 在实际应用中，会有导出按钮
    // 这里验证基本的UI功能
    expect(screen.getByText('车削外圆')).toBeInTheDocument();
  });

  test('用户场景: 工艺师预览PDF文档', async () => {
    // 这个测试需要PDF预览组件，这里验证基本交互
    render(
      <AssistantPanel
        onSendMessage={mockSendMessage}
        suggestions={mockSuggestions}
        isLoading={false}
        processDocument={mockProcessDocument}
      />
    );

    // 验证工艺文件内容显示
    expect(screen.getByText('主轴箱加工工艺')).toBeInTheDocument();

    // 用户可以查看完整的工艺内容
    expect(screen.getByText('使用数控车床加工外圆至尺寸要求')).toBeInTheDocument();
  });
});