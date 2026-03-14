import React, { useState } from 'react';
import { Card, Table, Button, Space, Input, Form, Modal, Select, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons';

interface ProcessOperation {
  id: string;
  sequence: number;
  name: string;
  description: string;
  tools: string[];
  parameters: Record<string, any>;
}

interface ProcessDocument {
  id: string;
  name: string;
  operations: ProcessOperation[];
  parameters: Record<string, any>;
  qualityRequirements: Array<{
    id: string;
    description: string;
    standard: string;
    tolerance: string;
  }>;
}

interface ProcessEditorProps {
  document: ProcessDocument;
  onChange: (updatedDoc: ProcessDocument) => void;
}

const ProcessEditor: React.FC<ProcessEditorProps> = ({ document, onChange }) => {
  const [editingOperation, setEditingOperation] = useState<ProcessOperation | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();

  const handleEdit = (operation: ProcessOperation) => {
    setEditingOperation(operation);
    form.setFieldsValue(operation);
    setIsModalVisible(true);
  };

  const handleDelete = (operationId: string) => {
    const updatedOperations = document.operations.filter(op => op.id !== operationId);
    onChange({
      ...document,
      operations: updatedOperations
    });
  };

  const handleAdd = () => {
    const newOperation: ProcessOperation = {
      id: `op_${Date.now()}`,
      sequence: document.operations.length + 1,
      name: '',
      description: '',
      tools: [],
      parameters: {}
    };
    setEditingOperation(newOperation);
    form.setFieldsValue(newOperation);
    setIsModalVisible(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const updatedOperations = editingOperation?.id
        ? document.operations.map(op =>
            op.id === editingOperation.id ? { ...values, id: editingOperation.id } : op
          )
        : [...document.operations, { ...values, id: `op_${Date.now()}` }];

      onChange({
        ...document,
        operations: updatedOperations
      });

      setIsModalVisible(false);
      form.resetFields();
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  const columns = [
    {
      title: '序号',
      dataIndex: 'sequence',
      key: 'sequence',
      width: 80
    },
    {
      title: '工序名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '工具',
      dataIndex: 'tools',
      key: 'tools',
      render: (tools: string[]) => (
        <Space size="small">
          {tools.map((tool, index) => (
            <Tag key={index} color="blue">{tool}</Tag>
          ))}
        </Space>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: ProcessOperation) => (
        <Space size="middle">
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            size="small"
          >
            编辑
          </Button>
          <Button
            type="link"
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
            size="small"
            danger
          >
            删除
          </Button>
        </Space>
      )
    }
  ];

  return (
    <Card title={`工艺文件: ${document.name}`} style={{ width: '100%' }}>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加工序
        </Button>
      </Space>

      <Table
        dataSource={document.operations}
        columns={columns}
        rowKey="id"
        pagination={false}
        size="small"
        scroll={{ y: 300 }}
      />

      <Modal
        title={editingOperation?.id ? '编辑工序' : '添加工序'}
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          form.resetFields();
        }}
        footer={[
          <Button
            key="cancel"
            icon={<CloseOutlined />}
            onClick={() => {
              setIsModalVisible(false);
              form.resetFields();
            }}
          >
            取消
          </Button>,
          <Button
            key="save"
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
          >
            保存
          </Button>
        ]}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="sequence"
            label="工序序号"
            rules={[{ required: true, message: '请输入工序序号' }]}
          >
            <Input type="number" min={1} />
          </Form.Item>

          <Form.Item
            name="name"
            label="工序名称"
            rules={[{ required: true, message: '请输入工序名称' }]}
          >
            <Input placeholder="例如：车削外圆" />
          </Form.Item>

          <Form.Item
            name="description"
            label="工序描述"
            rules={[{ required: true, message: '请输入工序描述' }]}
          >
            <Input.TextArea rows={3} placeholder="详细描述工序内容..." />
          </Form.Item>

          <Form.Item
            name="tools"
            label="使用工具"
          >
            <Select mode="tags" placeholder="输入或选择工具" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default ProcessEditor;