import React from 'react';
import { Card, Typography, Space, Tag, Tooltip } from 'antd';
import { FileTextOutlined, ClockCircleOutlined, DatabaseOutlined } from '@ant-design/icons';
import { PDFDocument } from '../../../services/pdfService';
import WarmCard from '../../ui/Card';

const { Text, Paragraph } = Typography;

interface DocumentCardProps {
  document: PDFDocument;
  isSelected: boolean;
  onClick: () => void;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({ document, isSelected, onClick }) => {
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (timestamp: number): string => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <WarmCard
      hoverable
      variant={isSelected ? 'elevated' : 'default'}
      onClick={onClick}
      style={{
        marginBottom: 12,
        borderColor: isSelected ? '#F5A623' : undefined,
        borderWidth: isSelected ? 2 : 1,
        cursor: 'pointer',
        transition: 'all 0.3s ease'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{
          background: isSelected ? '#F5A623' : '#f0f0f0',
          color: isSelected ? '#fff' : '#666',
          borderRadius: 8,
          padding: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: 40,
          height: 40
        }}>
          <FileTextOutlined style={{ fontSize: 18 }} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
            <Tooltip title={document.name}>
              <Paragraph strong ellipsis style={{ margin: 0, maxWidth: '70%' }}>
                {document.name}
              </Paragraph>
            </Tooltip>

            <Space size={4}>
              <Tag color={document.has_extracted ? 'success' : 'default'} icon={<DatabaseOutlined />}>
                {document.has_extracted ? '已提取' : '未提取'}
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {formatFileSize(document.size)}
              </Text>
            </Space>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
            <Space size={4}>
              <ClockCircleOutlined style={{ fontSize: 12, color: '#999' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                {formatDate(document.created_at)}
              </Text>
            </Space>

            {document.extracted_path && (
              <Tag color="blue" style={{ fontSize: 11, padding: '0 6px' }}>
                已缓存
              </Tag>
            )}
          </div>

          <div style={{ marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              路径: {document.path}
            </Text>
          </div>
        </div>
      </div>
    </WarmCard>
  );
};