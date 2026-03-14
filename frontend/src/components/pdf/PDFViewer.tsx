import React, { useState, useEffect, useRef } from 'react';
import { Card, Spin, Alert, Button, Space, Select, Typography } from 'antd';
import { LoadingOutlined, DownloadOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface PDFViewerProps {
  pdfData: ArrayBuffer | string;
  filename?: string;
  onLoad?: () => void;
  onError?: (error: string) => void;
}

const PDFViewer: React.FC<PDFViewerProps> = ({ pdfData, filename = 'document.pdf', onLoad, onError }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const loadPDF = async () => {
      try {
        setLoading(true);
        setError(null);

        // 模拟PDF加载过程
        // 在实际应用中，这里会调用WebAssembly PDF解析器
        await new Promise(resolve => setTimeout(resolve, 1000));

        // 模拟PDF信息
        setTotalPages(5);
        setCurrentPage(1);

        if (onLoad) {
          onLoad();
        }
      } catch (err) {
        const errorMessage = `PDF加载失败: ${(err as Error).message}`;
        setError(errorMessage);
        if (onError) {
          onError(errorMessage);
        }
      } finally {
        setLoading(false);
      }
    };

    if (pdfData) {
      loadPDF();
    }
  }, [pdfData, onLoad, onError]);

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 0.2, 3.0));
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 0.2, 0.5));
  };

  const handleDownload = () => {
    // 模拟下载功能
    const blob = new Blob([new Uint8Array([/* PDF data */])], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <Card style={{ height: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
          <Text style={{ marginLeft: 16 }}>正在加载PDF...</Text>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card style={{ height: '100%' }}>
        <Alert
          message="PDF加载失败"
          description={error}
          type="error"
          showIcon
        />
      </Card>
    );
  }

  return (
    <Card
      title="PDF预览"
      extra={
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleDownload}>
            下载
          </Button>
        </Space>
      }
      style={{ height: '100%' }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Toolbar */}
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button
              icon={<ZoomOutOutlined />}
              onClick={handleZoomOut}
              disabled={zoomLevel <= 0.5}
            />
            <Text>{Math.round(zoomLevel * 100)}%</Text>
            <Button
              icon={<ZoomInOutlined />}
              onClick={handleZoomIn}
              disabled={zoomLevel >= 3.0}
            />
          </Space>
          <Space>
            <Button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              上一页
            </Button>
            <Select
              value={currentPage}
              onChange={handlePageChange}
              style={{ width: 120 }}
            >
              {Array.from({ length: totalPages }, (_, i) => (
                <Select.Option key={i + 1} value={i + 1}>
                  第 {i + 1} 页 / {totalPages}
                </Select.Option>
              ))}
            </Select>
            <Button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
            >
              下一页
            </Button>
          </Space>
        </div>

        {/* PDF Canvas */}
        <div style={{ flex: 1, overflow: 'auto', border: '1px solid #e8e8e8', borderRadius: 4 }}>
          <canvas
            ref={canvasRef}
            style={{
              width: '100%',
              height: '100%',
              transform: `scale(${zoomLevel})`,
              transformOrigin: 'top left'
            }}
          />
          {/* 模拟PDF内容 */}
          <div style={{
            padding: 20,
            fontFamily: 'monospace',
            whiteSpace: 'pre-wrap'
          }}>
            {`PDF页面 ${currentPage} 的内容...\n\n这是工艺文件的第 ${currentPage} 页。\n支持离线预览和高精度渲染。`}
          </div>
        </div>
      </div>
    </Card>
  );
};

export default PDFViewer;