import React from 'react';
import { Input, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';

interface TerminalInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onKeyPress?: (e: React.KeyboardEvent) => void;
  disabled?: boolean;
  placeholder?: string;
}

const TerminalInput: React.FC<TerminalInputProps> = ({
  value,
  onChange,
  onSend,
  onKeyPress,
  disabled = false,
  placeholder = '输入您的工艺需求...'
}) => {
  return (
    <Space.Compact style={{ width: '100%' }}>
      <Input.TextArea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyPress={onKeyPress}
        disabled={disabled}
        placeholder={placeholder}
        autoSize={{ minRows: 1, maxRows: 4 }}
        style={{
          fontFamily: 'monospace',
          fontSize: 14,
          border: '1px solid #d9d9d9',
          borderRadius: '4px 0 0 4px'
        }}
      />
      <button
        onClick={onSend}
        disabled={disabled || !value.trim()}
        style={{
          height: '100%',
          padding: '0 16px',
          backgroundColor: disabled || !value.trim() ? '#f5f5f5' : '#1890ff',
          color: disabled || !value.trim() ? '#bfbfbf' : 'white',
          border: '1px solid #d9d9d9',
          borderLeft: 'none',
          borderRadius: '0 4px 4px 0',
          cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        <SendOutlined />
      </button>
    </Space.Compact>
  );
};

export default TerminalInput;