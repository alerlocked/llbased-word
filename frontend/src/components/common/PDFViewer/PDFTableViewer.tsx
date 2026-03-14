import React, { useState, useMemo } from 'react';
import { Table, Select, Typography, Space, Tag, Card, Empty } from 'antd';
import { FilterOutlined, TableOutlined } from '@ant-design/icons';
import { PDFTable } from '../../../services/pdfService';
import WarmCard from '../../ui/Card';

const { Title, Text } = Typography;
const { Option } = Select;

interface PDFTableViewerProps {
  tables: PDFTable[];
  loading?: boolean;
}

export const PDFTableViewer: React.FC<PDFTableViewerProps> = ({ tables, loading = false }) => {
  const [selectedPage, setSelectedPage] = useState<number | 'all'>('all');
  const [selectedType, setSelectedType] = useState<string | 'all'>('all');

  // 提取唯一的页面和表格类型
  const uniquePages = useMemo(() => {
    const pages = Array.from(new Set(tables.map(table => table.page_number)));
    return pages.sort((a, b) => a - b);
  }, [tables]);

  const uniqueTypes = useMemo(() => {
    const types = Array.from(new Set(tables.map(table => table.table_type)));
    return types.sort();
  }, [tables]);

  // 过滤表格数据
  const filteredTables = useMemo(() => {
    return tables.filter(table => {
      const pageMatch = selectedPage === 'all' || table.page_number === selectedPage;
      const typeMatch = selectedType === 'all' || table.table_type === selectedType;
      return pageMatch && typeMatch;
    });
  }, [tables, selectedPage, selectedType]);

  // 准备表格数据
  const tableData = useMemo(() => {
    return filteredTables.map((table, index) => ({
      key: `${table.table_id}_${index}`,
      id: table.table_id,
      page: table.page_number,
      type: table.table_type,
      method: table.method,
      rows: table.row_count,
      cols: table.col_count,
      table: table,
    }));
  }, [filteredTables]);

  // 表格列定义
  const columns = [
    {
      title: '表格ID',
      dataIndex: 'id',
      key: 'id',
      width: 120,
      render: (id: string) => (
        <Text code style={{ fontSize: 12 }}>
          {id}
        </Text>
      ),
    },
    {
      title: '页码',
      dataIndex: 'page',
      key: 'page',
      width: 80,
      render: (page: number) => (
        <Tag color="blue">第 {page} 页</Tag>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => {
        const typeColors: Record<string, string> = {
          'process_cards': 'green',
          'operation_cards': 'orange',
          'tool_lists': 'purple',
          'parameter_tables': 'cyan',
          'general_table': 'default',
        };
        return (
          <Tag color={typeColors[type] || 'default'}>
            {type === 'process_cards' ? '工艺卡片' :
             type === 'operation_cards' ? '工序卡片' :
             type === 'tool_lists' ? '工具清单' :
             type === 'parameter_tables' ? '参数表' : type}
          </Tag>
        );
      },
    },
    {
      title: '提取方法',
      dataIndex: 'method',
      key: 'method',
      width: 100,
    },
    {
      title: '尺寸',
      dataIndex: 'rows',
      key: 'size',
      width: 100,
      render: (rows: number, record: any) => (
        <Text type="secondary">
          {rows} × {record.cols}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Space>
          <a onClick={() => handleViewTable(record.table)}>查看</a>
          <a onClick={() => handleExportTable(record.table)}>导出</a>
        </Space>
      ),
    },
  ];

  const handleViewTable = (table: PDFTable) => {
    // 这里可以打开一个模态框显示表格详情
    console.log('查看表格:', table);
  };

  const handleExportTable = (table: PDFTable) => {
    // 这里可以实现表格导出功能
    console.log('导出表格:', table);
  };

  if (tables.length === 0) {
    return (
      <WarmCard variant="default" style={{ textAlign: 'center', padding: 40 }}>
        <Empty
          image={<TableOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
          description="暂无表格数据"
        />
      </WarmCard>
    );
  }

  return (
    <div>
      <WarmCard variant="default" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={5} style={{ margin: 0 }}>
            表格数据
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 14 }}>
              ({tables.length} 个表格)
            </Text>
          </Title>
          <Space>
            <Select
              value={selectedPage}
              onChange={setSelectedPage}
              style={{ width: 120 }}
              placeholder="选择页码"
              suffixIcon={<FilterOutlined />}
            >
              <Option value="all">所有页码</Option>
              {uniquePages.map(page => (
                <Option key={page} value={page}>
                  第 {page} 页
                </Option>
              ))}
            </Select>

            <Select
              value={selectedType}
              onChange={setSelectedType}
              style={{ width: 120 }}
              placeholder="选择类型"
              suffixIcon={<FilterOutlined />}
            >
              <Option value="all">所有类型</Option>
              {uniqueTypes.map(type => (
                <Option key={type} value={type}>
                  {type === 'process_cards' ? '工艺卡片' :
                   type === 'operation_cards' ? '工序卡片' :
                   type === 'tool_lists' ? '工具清单' :
                   type === 'parameter_tables' ? '参数表' : type}
                </Option>
              ))}
            </Select>
          </Space>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            显示 {filteredTables.length} 个表格
            {selectedPage !== 'all' && `，页码: ${selectedPage}`}
            {selectedType !== 'all' && `，类型: ${selectedType}`}
          </Text>
        </div>
      </WarmCard>

      <Table
        columns={columns}
        dataSource={tableData}
        loading={loading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 个表格`,
        }}
        expandable={{
          expandedRowRender: (record) => (
            <Card size="small" title="表格预览" style={{ margin: '8px 0' }}>
              <div style={{ maxHeight: 300, overflow: 'auto' }}>
                <Table
                  size="small"
                  dataSource={record.table.rows.map((row, index) => ({
                    key: index,
                    cells: row.cells,
                    text: row.text,
                  }))}
                  columns={record.table.rows[0]?.cells.map((_, colIndex) => ({
                    title: `列 ${colIndex + 1}`,
                    dataIndex: ['cells', colIndex],
                    key: `col_${colIndex}`,
                    render: (cell: string) => (
                      <div style={{ padding: '4px 8px', whiteSpace: 'nowrap' }}>
                        {cell}
                      </div>
                    ),
                  }))}
                  pagination={false}
                />
              </div>
            </Card>
          ),
          rowExpandable: (record) => record.table.rows.length > 0,
        }}
      />
    </div>
  );
};