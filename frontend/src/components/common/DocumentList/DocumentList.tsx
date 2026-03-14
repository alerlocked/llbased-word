import React, { useEffect } from 'react';
import { List, Typography, Spin, Empty, Button, Space, Alert } from 'antd';
import { ReloadOutlined, FileSearchOutlined } from '@ant-design/icons';
import { useCreationStore } from '../../../stores/creationStore';
import { DocumentCard } from './DocumentCard';
import WarmCard from '../../ui/Card';

const { Title, Text } = Typography;

interface DocumentListProps {
  selectedDocumentId?: string;
  onDocumentSelect: (documentId: string) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  selectedDocumentId,
  onDocumentSelect
}) => {
  const {
    pdfDocuments,
    pdfLoading,
    pdfError,
    loadPDFDocuments,
    clearPDFError
  } = useCreationStore();

  useEffect(() => {
    loadPDFDocuments();
  }, [loadPDFDocuments]);

  const handleRefresh = () => {
    clearPDFError();
    loadPDFDocuments();
  };

  if (pdfError) {
    return (
      <WarmCard variant="default">
        <Alert
          message="加载失败"
          description={pdfError}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={handleRefresh}>
              重试
            </Button>
          }
        />
      </WarmCard>
    );
  }

  if (pdfLoading && pdfDocuments.length === 0) {
    return (
      <WarmCard variant="default" style={{ textAlign: 'center', padding: 40 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">正在加载文档列表...</Text>
        </div>
      </WarmCard>
    );
  }

  if (pdfDocuments.length === 0) {
    return (
      <WarmCard variant="default" style={{ textAlign: 'center', padding: 40 }}>
        <Empty
          image={<FileSearchOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
          description={
            <div>
              <Text type="secondary">暂无工艺文档</Text>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  请在后端添加PDF文档到 data/process_docs/ 目录
                </Text>
              </div>
            </div>
          }
        />
      </WarmCard>
    );
  }

  return (
    <WarmCard variant="default">
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={5} style={{ margin: 0 }}>
            工艺文档列表
          </Title>
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>
              共 {pdfDocuments.length} 个文档
            </Text>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={pdfLoading}
              onClick={handleRefresh}
            >
              刷新
            </Button>
          </Space>
        </div>
      </div>

      <div style={{ maxHeight: 500, overflowY: 'auto', paddingRight: 4 }}>
        {pdfDocuments.map((document) => (
          <DocumentCard
            key={document.id}
            document={document}
            isSelected={selectedDocumentId === document.id}
            onClick={() => onDocumentSelect(document.id)}
          />
        ))}
      </div>

      <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          点击文档查看提取的表格、工具清单和工艺参数
        </Text>
      </div>
    </WarmCard>
  );
};