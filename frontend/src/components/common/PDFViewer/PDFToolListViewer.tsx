import React from 'react';
import { Table, Typography, Tag, Empty } from 'antd';
import { ToolOutlined, DatabaseOutlined } from '@ant-design/icons';
import { PDFToolItem } from '../../../services/pdfService';
import WarmCard from '../../ui/Card';

const { Title, Text } = Typography;

interface PDFToolListViewerProps {
  tools: PDFToolItem[];
  loading?: boolean;
}

export const PDFToolListViewer: React.FC<PDFToolListViewerProps> = ({ tools, loading = false }) => {
  // 表格列定义
  const columns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string) => (
        <Text strong>{name}</Text>
      ),
    },
    {
      title: '规格型号',
      dataIndex: 'specification',
      key: 'specification',
      width: 250,
      render: (specification: string) => (
        specification ? (
          <Text code style={{ fontSize: 12 }}>
            {specification}
          </Text>
        ) : (
          <Text type="secondary">无规格信息</Text>
        )
      ),
    },
    {
      title: '位置',
      key: 'location',
      width: 120,
      render: (_: any, record: PDFToolItem) => (
        <Tag color="blue">
          第 {record.page} 页
        </Tag>
      ),
    },
    {
      title: '行索引',
      dataIndex: 'row_index',
      key: 'row_index',
      width: 80,
      render: (rowIndex: number) => (
        <Text type="secondary">{rowIndex}</Text>
      ),
    },
  ];

  if (tools.length === 0) {
    return (
      <WarmCard variant="default" style={{ textAlign: 'center', padding: 40 }}>
        <Empty
          image={<ToolOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
          description="暂无工具清单数据"
        />
      </WarmCard>
    );
  }

  return (
    <div>
      <WarmCard variant="default" style={{ marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>
          工具清单
          <Text type="secondary" style={{ marginLeft: 8, fontSize: 14 }}>
            ({tools.length} 个工具)
          </Text>
        </Title>
        <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
          从工艺文档中提取的工具信息，包含名称、规格和位置
        </Text>
      </WarmCard>

      <Table
        columns={columns}
        dataSource={tools.map((tool, index) => ({
          key: `${tool.name}_${index}`,
          ...tool,
        }))}
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 个工具`,
        }}
        size="small"
      />
    </div>
  );
};