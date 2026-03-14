import React, { useState } from 'react';
import { Button, Dropdown, MenuProps, message, Modal, Progress } from 'antd';
import { DownloadOutlined, LoadingOutlined } from '@ant-design/icons';
import { usePdfDocumentStore } from '../../../stores/pdfDocumentStore';
import { csvExportService } from '../../../services/csvExportService';

interface CSVExportButtonProps {
  docId: string;
  disabled?: boolean;
}

const CSVExportButton: React.FC<CSVExportButtonProps> = ({ docId, disabled = false }) => {
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [showProgress, setShowProgress] = useState(false);

  const { tables, selectedTables } = usePdfDocumentStore();

  const handleExport = async (exportType: 'single' | 'selected' | 'all' | 'batch') => {
    try {
      setLoading(true);
      setShowProgress(true);
      setProgress(0);

      let tableIds: string[] = [];

      if (exportType === 'single' && selectedTables.length > 0) {
        tableIds = [selectedTables[0]];
      } else if (exportType === 'selected' && selectedTables.length > 0) {
        tableIds = selectedTables;
      } else if (exportType === 'all') {
        tableIds = tables.map(table => table.table_id);
      }

      // Start export
      const result = await csvExportService.exportToCSV(docId, {
        tableIds,
        includeMetadata: true,
        mergeMultipage: true
      });

      // Simulate progress for demonstration
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 100) {
            clearInterval(interval);
            return 100;
          }
          return prev + 10;
        });
      }, 200);

      // Wait for completion
      setTimeout(() => {
        clearInterval(interval);
        setProgress(100);
        setLoading(false);
        setShowProgress(false);

        message.success(`导出成功！共导出 ${result.total_tables} 个表格`);

        // Trigger download
        window.location.href = result.download_url;
      }, 2000);

    } catch (error) {
      setLoading(false);
      setShowProgress(false);
      message.error('导出失败，请重试');
      console.error('CSV export failed:', error);
    }
  };

  const items: MenuProps['items'] = [
    {
      key: 'single',
      label: '导出选中表格',
      disabled: selectedTables.length !== 1,
    },
    {
      key: 'selected',
      label: '导出选中表格（多个）',
      disabled: selectedTables.length <= 1,
    },
    {
      key: 'all',
      label: '导出所有表格',
      disabled: tables.length === 0,
    },
    {
      key: 'batch',
      label: '批量导出（多个文档）',
      disabled: true, // Will be implemented later
    },
  ];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    handleExport(key as any);
  };

  return (
    <div className="csv-export-button">
      <Dropdown
        menu={{ items, onClick: handleMenuClick }}
        disabled={disabled || loading}
        placement="bottomRight"
      >
        <Button
          type="primary"
          icon={loading ? <LoadingOutlined /> : <DownloadOutlined />}
          disabled={disabled}
        >
          导出CSV
        </Button>
      </Dropdown>

      {showProgress && (
        <Modal
          title="导出进度"
          open={true}
          footer={null}
          closable={false}
        >
          <Progress percent={progress} status="active" />
          <p style={{ marginTop: 16 }}>
            正在导出表格数据...
          </p>
        </Modal>
      )}
    </div>
  );
};

export default CSVExportButton;