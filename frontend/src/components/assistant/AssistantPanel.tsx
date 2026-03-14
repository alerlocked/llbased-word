import React, { useState, useEffect } from 'react';
import { Card, Space, Typography, Input, Button, Spin, Alert } from 'antd';
import { SendOutlined, LoadingOutlined } from '@ant-design/icons';
import SuggestionCard from './SuggestionCard';
import TerminalInput from './TerminalInput';
import ProcessEditor from './ProcessEditor';

const { Title, Text } = Typography;

interface AssistantPanelProps {
  onSendMessage: (message: string) => Promise<void>;
  suggestions: Array<{
    id: string;
    type: string;
    content: string;
    confidence: number;
    actions: Array<{ label: string; action: () => void }>;
  }>;
  isLoading: boolean;
  error?: string;
  processDocument?: any;
}

const AssistantPanel: React.FC<AssistantPanelProps> = ({
  onSendMessage,
  suggestions = [],
  isLoading,
  error,
  processDocument
}) => {
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSend = async () => {
    if (!inputValue.trim() || isProcessing) return;

    setIsProcessing(true);
    try {
      await onSendMessage(inputValue);
      setInputValue('');
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Card className="assistant-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>工艺文件助理</Title>
        <Text type="secondary">
          输入您的工艺需求，我将帮助您生成标准的工艺文件
        </Text>
      </div>

      {error && (
        <Alert
          message="操作失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Suggestions Section */}
      {suggestions.length > 0 && (
        <div style={{ marginBottom: 16, maxHeight: 200, overflowY: 'auto' }}>
          <Text strong>建议:</Text>
          <Space direction="vertical" style={{ width: '100%', marginTop: 8 }}>
            {suggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
              />
            ))}
          </Space>
        </div>
      )}

      {/* Process Editor */}
      {processDocument && (
        <div style={{ flex: 1, marginBottom: 16, overflow: 'auto' }}>
          <ProcessEditor
            document={processDocument}
            onChange={(updatedDoc) => {
              // Handle document updates
              console.log('Document updated:', updatedDoc);
            }}
          />
        </div>
      )}

      {/* Input Section */}
      <div style={{ marginTop: 'auto' }}>
        <TerminalInput
          value={inputValue}
          onChange={setInputValue}
          onSend={handleSend}
          onKeyPress={handleKeyPress}
          disabled={isProcessing}
          placeholder="例如：为零件A创建车削工艺..."
        />
        <div style={{ textAlign: 'right', marginTop: 8 }}>
          <Button
            type="primary"
            icon={isProcessing ? <LoadingOutlined /> : <SendOutlined />}
            onClick={handleSend}
            disabled={!inputValue.trim() || isProcessing}
            loading={isProcessing}
          >
            {isProcessing ? '处理中...' : '发送'}
          </Button>
        </div>
      </div>

      {isLoading && (
        <div style={{ textAlign: 'center', padding: 16 }}>
          <Spin tip="正在处理您的请求..." />
        </div>
      )}
    </Card>
  );
};

export default AssistantPanel;