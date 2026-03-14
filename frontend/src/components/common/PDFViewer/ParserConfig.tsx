import React, { useState, useEffect } from 'react';
import { Card, Select, Slider, Switch, message, Button, Space, Typography } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { usePdfDocumentStore } from '../../../stores/pdfDocumentStore';
import { csvExportService } from '../../../services/csvExportService';

const { Option } = Select;
const { Text } = Typography;

interface ParserConfigProps {
  docId: string;
}

const ParserConfig: React.FC<ParserConfigProps> = ({ docId }) => {
  const [loading, setLoading] = useState(false);
  const [parserConfig, setParserConfig] = useState<any>(null);
  const [csvConfig, setCSVConfig] = useState<any>(null);

  const { updateParserSettings } = usePdfDocumentStore();

  useEffect(() => {
    loadConfigs();
  }, [docId]);

  const loadConfigs = async () => {
    try {
      setLoading(true);

      // Load parser config
      const parserConfigData = await csvExportService.getParserConfig(docId);
      setParserConfig(parserConfigData);

      // Load CSV config
      const csvConfigData = await csvExportService.getCSVConfig();
      setCSVConfig(csvConfigData);

    } catch (error) {
      message.error('加载配置失败');
      console.error('Failed to load configs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleParserChange = (value: string) => {
    const newConfig = { ...parserConfig, recommended_parser: value };
    setParserConfig(newConfig);
    updateParserSettings(newConfig);
  };

  const handleAccuracyThresholdChange = (value: number) => {
    const newConfig = { ...parserConfig, analysis_details: { ...parserConfig.analysis_details, accuracy_threshold: value } };
    setParserConfig(newConfig);
    updateParserSettings(newConfig);
  };

  const handleMultipageMergeChange = (checked: boolean) => {
    const newConfig = { ...parserConfig, analysis_details: { ...parserConfig.analysis_details, enable_multipage_merge: checked } };
    setParserConfig(newConfig);
    updateParserSettings(newConfig);
  };

  const handleCSVEncodingChange = (value: string) => {
    const newConfig = { ...csvConfig, encoding: value };
    setCSVConfig(newConfig);
    // Update CSV config in store if needed
  };

  const handleIncludeMetadataChange = (checked: boolean) => {
    const newConfig = { ...csvConfig, include_metadata: checked };
    setCSVConfig(newConfig);
  };

  return (
    <Card
      title={
        <Space>
          <SettingOutlined />
          <Text strong>解析器配置</Text>
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
    >
      {loading && <Text type="secondary">加载中...</Text>}

      {!loading && parserConfig && (
        <>
          <div style={{ marginBottom: 16 }}>
            <Text strong>推荐解析器:</Text>
            <Text type="secondary" style={{ marginLeft: 8 }}>
              {parserConfig.reasoning}
            </Text>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text strong>解析器选择:</Text>
            <Select
              value={parserConfig.recommended_parser}
              onChange={handleParserChange}
              style={{ width: '100%', marginTop: 8 }}
            >
              <Option value="auto">自动选择</Option>
              <Option value="pymupdf">PyMuPDF (快速)</Option>
              <Option value="pdfplumber">pdfplumber (高精度)</Option>
              <Option value="hybrid">混合模式</Option>
            </Select>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text strong>准确性阈值:</Text>
            <Slider
              min={0.90}
              max={0.99}
              step={0.01}
              value={parserConfig.config?.accuracy_threshold || 0.97}
              onChange={handleAccuracyThresholdChange}
              style={{ marginTop: 8 }}
              tooltip={{ formatter: (value) => `${(value! * 100).toFixed(0)}%` }}
            />
            <Text type="secondary" style={{ marginTop: 4 }}>
              当前: {(parserConfig.config?.accuracy_threshold || 0.97) * 100}%
            </Text>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Space>
              <Switch
                checked={parserConfig.config?.enable_multipage_merge || false}
                onChange={handleMultipageMergeChange}
              />
              <Text>合并跨页表格</Text>
            </Space>
          </div>

          {csvConfig && (
            <>
              <div style={{ marginBottom: 16, marginTop: 24 }}>
                <Text strong>CSV导出配置:</Text>
              </div>

              <div style={{ marginBottom: 16 }}>
                <Text strong>编码:</Text>
                <Select
                  value={csvConfig.encoding}
                  onChange={handleCSVEncodingChange}
                  style={{ width: '100%', marginTop: 8 }}
                >
                  <Option value="utf-8-sig">UTF-8 BOM (Excel兼容)</Option>
                  <Option value="utf-8">UTF-8</Option>
                </Select>
              </div>

              <div style={{ marginBottom: 16 }}>
                <Space>
                  <Switch
                    checked={csvConfig.include_metadata}
                    onChange={handleIncludeMetadataChange}
                  />
                  <Text>包含元数据</Text>
                </Space>
              </div>
            </>
          )}

          <Button
            type="primary"
            onClick={loadConfigs}
            style={{ marginTop: 16 }}
          >
            刷新分析
          </Button>
        </>
      )}
    </Card>
  );
};

export default ParserConfig;