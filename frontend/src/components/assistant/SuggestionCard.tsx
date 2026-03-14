import React from 'react';
import { Card, Tag, Button, Space } from 'antd';
import { CheckCircleOutlined, InfoCircleOutlined, WarningOutlined } from '@ant-design/icons';

interface Suggestion {
  id: string;
  type: string;
  content: string;
  confidence: number;
  actions: Array<{ label: string; action: () => void }>;
}

interface SuggestionCardProps {
  suggestion: Suggestion;
}

const SuggestionCard: React.FC<SuggestionCardProps> = ({ suggestion }) => {
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'green';
    if (confidence >= 0.7) return 'blue';
    return 'orange';
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'terminology':
        return <InfoCircleOutlined />;
      case 'compliance':
        return <WarningOutlined />;
      case 'suggestion':
        return <CheckCircleOutlined />;
      default:
        return <InfoCircleOutlined />;
    }
  };

  const getTypeTag = (type: string) => {
    switch (type) {
      case 'terminology':
        return '术语建议';
      case 'compliance':
        return '合规提醒';
      case 'suggestion':
        return '优化建议';
      default:
        return type;
    }
  };

  return (
    <Card size="small" style={{ width: '100%' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            {getTypeIcon(suggestion.type)}
            <Tag color={getConfidenceColor(suggestion.confidence)}>
              {getTypeTag(suggestion.type)} • {(suggestion.confidence * 100).toFixed(0)}%
            </Tag>
          </Space>
        </div>
        <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
          {suggestion.content}
        </div>
        {suggestion.actions && suggestion.actions.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Space>
              {suggestion.actions.map((action, index) => (
                <Button key={index} size="small" onClick={action.action}>
                  {action.label}
                </Button>
              ))}
            </Space>
          </div>
        )}
      </Space>
    </Card>
  );
};

export default SuggestionCard;