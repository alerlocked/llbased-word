/**
 * WasmPDFViewer - WebAssembly PDF 预览组件
 * 基于 pdfjs-dist 实现高性能 PDF 渲染
 * 主题配色：蓝(#1890ff) 白(#ffffff) 灰(#f0f2f5)
 */
import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Button, Space, Slider, InputNumber, Spin, message, Tooltip } from 'antd';
import {
  ZoomInOutlined,
  ZoomOutOutlined,
  LeftOutlined,
  RightOutlined,
  RotateRightOutlined,
  ReloadOutlined,
  DownloadOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
} from '@ant-design/icons';
import * as pdfjsLib from 'pdfjs-dist';

// 设置 WebAssembly worker - 使用本地文件提高稳定性
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

interface WasmPDFViewerProps {
  /** PDF 文件 URL 或 ArrayBuffer */
  src: string | ArrayBuffer;
  /** 初始缩放比例 (0.5 - 3.0) */
  initialScale?: number;
  /** 容器高度 */
  height?: number | string;
  /** 加载完成回调 */
  onLoad?: (pdfInfo: { totalPages: number; title: string }) => void;
  /** 错误回调 */
  onError?: (error: Error) => void;
  /** 页面变化回调 */
  onPageChange?: (page: number) => void;
  /** 缩放变化回调 */
  onScaleChange?: (scale: number) => void;
}

interface PDFState {
  pdfDoc: pdfjsLib.PDFDocumentProxy | null;
  currentPage: number;
  totalPages: number;
  scale: number;
  rotation: number;
  loading: boolean;
  error: string | null;
  isFullscreen: boolean;
}

// 主题配色常量
const THEME = {
  primary: '#1890ff',
  primaryHover: '#40a9ff',
  background: '#f0f2f5',
  white: '#ffffff',
  textPrimary: '#262626',
  textSecondary: '#595959',
  toolbarBg: '#ffffff',
  viewerBg: '#525659',
};

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3.0;
const ZOOM_STEP = 0.25;

export const WasmPDFViewer: React.FC<WasmPDFViewerProps> = ({
  src,
  initialScale = 1.0,
  height = 600,
  onLoad,
  onError,
  onPageChange,
  onScaleChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null);

  const [state, setState] = useState<PDFState>({
    pdfDoc: null,
    currentPage: 1,
    totalPages: 0,
    scale: initialScale,
    rotation: 0,
    loading: true,
    error: null,
    isFullscreen: false,
  });

  // 加载 PDF 文档
  useEffect(() => {
    let mounted = true;

    const loadPDF = async () => {
      try {
        setState(prev => ({ ...prev, loading: true, error: null }));

        const loadingTask = pdfjsLib.getDocument(src);
        const pdfDoc = await loadingTask.promise;

        if (!mounted) return;

        const title = (pdfDoc as any).getTitle?.() || 'Untitled';

        setState(prev => ({
          ...prev,
          pdfDoc,
          totalPages: pdfDoc.numPages,
          loading: false,
        }));

        onLoad?.({ totalPages: pdfDoc.numPages, title });
      } catch (err) {
        if (!mounted) return;

        const error = err as Error;
        setState(prev => ({
          ...prev,
          loading: false,
          error: error.message,
        }));
        onError?.(error);
        message.error(`PDF 加载失败: ${error.message}`);
      }
    };

    loadPDF();

    return () => {
      mounted = false;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [src, onLoad, onError]);

  // 渲染当前页面
  const renderPage = useCallback(async (pageNum: number, scale: number, rotation: number) => {
    const { pdfDoc } = state;
    if (!pdfDoc || !canvasRef.current || !textLayerRef.current) return;

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    try {
      const page = await pdfDoc.getPage(pageNum);
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');

      if (!context) return;

      const viewport = page.getViewport({ scale, rotation });

      canvas.height = viewport.height;
      canvas.width = viewport.width;

      const renderContext = {
        canvasContext: context,
        viewport,
      };

      renderTaskRef.current = page.render(renderContext as any);
      await renderTaskRef.current.promise;
      renderTaskRef.current = null;

      const textLayer = textLayerRef.current;
      textLayer.innerHTML = '';
      textLayer.style.width = `${viewport.width}px`;
      textLayer.style.height = `${viewport.height}px`;

      const textContent = await page.getTextContent();

      // 使用任何可用的文本层渲染方法
      (pdfjsLib as any).renderTextLayer?.({
        textContentSource: textContent,
        container: textLayer,
        viewport,
        textDivs: [],
      });
    } catch (err) {
      if ((err as Error).name !== 'RenderingCancelledException') {
        console.error('页面渲染错误:', err);
      }
    }
  }, [state]);

  useEffect(() => {
    if (state.pdfDoc && !state.loading) {
      renderPage(state.currentPage, state.scale, state.rotation);
    }
  }, [state.currentPage, state.scale, state.rotation, state.pdfDoc, state.loading, renderPage]);

  // 导航控制
  const goToPage = useCallback((page: number) => {
    const validPage = Math.max(1, Math.min(page, state.totalPages));
    if (validPage !== state.currentPage) {
      setState(prev => ({ ...prev, currentPage: validPage }));
      onPageChange?.(validPage);
    }
  }, [state.totalPages, state.currentPage, onPageChange]);

  const prevPage = useCallback(() => {
    goToPage(state.currentPage - 1);
  }, [state.currentPage, goToPage]);

  const nextPage = useCallback(() => {
    goToPage(state.currentPage + 1);
  }, [state.currentPage, goToPage]);

  // 缩放控制
  const handleZoom = useCallback((newScale: number) => {
    const clampedScale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, newScale));
    setState(prev => ({ ...prev, scale: clampedScale }));
    onScaleChange?.(clampedScale);
  }, [onScaleChange]);

  const zoomIn = useCallback(() => {
    handleZoom(state.scale + ZOOM_STEP);
  }, [state.scale, handleZoom]);

  const zoomOut = useCallback(() => {
    handleZoom(state.scale - ZOOM_STEP);
  }, [state.scale, handleZoom]);

  // 旋转控制
  const rotate = useCallback(() => {
    setState(prev => ({
      ...prev,
      rotation: (prev.rotation + 90) % 360,
    }));
  }, []);

  // 全屏切换
  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current?.parentElement;
    if (!container) return;

    if (!document.fullscreenElement) {
      container.requestFullscreen?.().then(() => {
        setState(prev => ({ ...prev, isFullscreen: true }));
      }).catch((err) => {
        message.warning('无法进入全屏模式');
        console.error('全屏错误:', err);
      });
    } else {
      document.exitFullscreen?.().then(() => {
        setState(prev => ({ ...prev, isFullscreen: false }));
      }).catch((err) => {
        console.error('退出全屏错误:', err);
      });
    }
  }, []);

  // 监听全屏变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setState(prev => ({
        ...prev,
        isFullscreen: !!document.fullscreenElement,
      }));
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // 下载PDF
  const handleDownload = useCallback(async () => {
    if (typeof src === 'string') {
      try {
        const response = await fetch(src);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = src.split('/').pop() || 'document.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        message.success('下载已开始');
      } catch (err) {
        message.error('下载失败');
        console.error('下载错误:', err);
      }
    } else if (src instanceof ArrayBuffer) {
      const blob = new Blob([src], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'document.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('下载已开始');
    }
  }, [src]);

  const scalePercent = useMemo(() => Math.round(state.scale * 100), [state.scale]);

  // 加载中状态
  if (state.loading) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: THEME.background,
          borderRadius: 8,
        }}
      >
        <Spin size="large" tip="加载 PDF 中...">
          <div style={{ padding: 50 }} />
        </Spin>
      </div>
    );
  }

  // 错误状态
  if (state.error) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: THEME.background,
          borderRadius: 8,
          border: `1px solid ${THEME.primary}33`,
          padding: 24,
        }}
      >
        <ReloadOutlined style={{ fontSize: 32, color: THEME.primary, marginBottom: 16 }} />
        <p style={{ color: THEME.textPrimary, margin: 0, fontWeight: 500 }}>PDF 加载失败</p>
        <p style={{ color: THEME.textSecondary, fontSize: 12, marginTop: 8 }}>{state.error}</p>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={() => window.location.reload()}
          style={{ marginTop: 16, background: THEME.primary, borderColor: THEME.primary }}
        >
          重新加载
        </Button>
      </div>
    );
  }

  return (
    <div
      className="wasm-pdf-viewer"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: state.isFullscreen ? THEME.viewerBg : 'transparent',
      }}
    >
      {/* 工具栏 */}
      <div
        style={{
          padding: '8px 16px',
          background: THEME.toolbarBg,
          borderBottom: `1px solid ${THEME.background}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 8,
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        }}
      >
        {/* 页面导航 */}
        <Space>
          <Tooltip title="上一页">
            <Button
              icon={<LeftOutlined />}
              onClick={prevPage}
              disabled={state.currentPage <= 1}
              aria-label="上一页"
            />
          </Tooltip>

          <Space.Compact>
            <InputNumber
              min={1}
              max={state.totalPages}
              value={state.currentPage}
              onChange={(val) => val && goToPage(val)}
              style={{ width: 60 }}
              role="spinbutton"
            />
            <Button disabled>/ {state.totalPages}</Button>
          </Space.Compact>

          <Tooltip title="下一页">
            <Button
              icon={<RightOutlined />}
              onClick={nextPage}
              disabled={state.currentPage >= state.totalPages}
              aria-label="下一页"
            />
          </Tooltip>
        </Space>

        {/* 缩放控制 */}
        <Space>
          <Tooltip title="缩小">
            <Button
              icon={<ZoomOutOutlined />}
              onClick={zoomOut}
              disabled={state.scale <= ZOOM_MIN}
              aria-label="缩小"
            />
          </Tooltip>

          <Slider
            min={ZOOM_MIN * 100}
            max={ZOOM_MAX * 100}
            step={ZOOM_STEP * 100}
            value={scalePercent}
            onChange={(val) => handleZoom(val / 100)}
            style={{ width: 120 }}
            tooltip={{ formatter: (val) => `${val}%` }}
          />

          <InputNumber
            min={ZOOM_MIN * 100}
            max={ZOOM_MAX * 100}
            step={ZOOM_STEP * 100}
            value={scalePercent}
            onChange={(val) => val && handleZoom(val / 100)}
            formatter={(val) => `${val}%`}
            parser={(val) => val?.replace('%', '') as unknown as number}
            style={{ width: 80 }}
            role="spinbutton"
          />

          <Tooltip title="放大">
            <Button
              icon={<ZoomInOutlined />}
              onClick={zoomIn}
              disabled={state.scale >= ZOOM_MAX}
              aria-label="放大"
            />
          </Tooltip>
        </Space>

        {/* 其他操作 */}
        <Space>
          <Tooltip title="旋转 (顺时针90°)">
            <Button
              icon={<RotateRightOutlined />}
              onClick={rotate}
              style={{ color: THEME.textSecondary }}
              aria-label="旋转"
            />
          </Tooltip>
          <Tooltip title={state.isFullscreen ? "退出全屏" : "全屏"}>
            <Button
              icon={state.isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={toggleFullscreen}
              style={{ color: THEME.textSecondary }}
              aria-label={state.isFullscreen ? "退出全屏" : "全屏"}
            />
          </Tooltip>
          <Tooltip title="下载">
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              style={{ background: THEME.primary, borderColor: THEME.primary }}
              aria-label="下载"
            />
          </Tooltip>
        </Space>
      </div>

      {/* PDF 内容区域 */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          background: THEME.viewerBg,
          padding: 16,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
        }}
      >
        <div style={{ position: 'relative' }}>
          <canvas
            ref={canvasRef}
            style={{
              display: 'block',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              borderRadius: 4,
            }}
          />
          <div
            ref={textLayerRef}
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              overflow: 'hidden',
              opacity: 0.2,
              lineHeight: 1,
            }}
            className="textLayer"
          />
        </div>
      </div>

      {/* 样式：文本层选择效果 - 蓝色主题 */}
      <style>{`
        .textLayer {
          user-select: text;
        }
        .textLayer ::selection {
          background: rgba(24, 144, 255, 0.3);
        }
        .textLayer span {
          color: transparent;
          position: absolute;
          white-space: pre;
          cursor: text;
          transform-origin: 0 0;
        }
        .wasm-pdf-viewer ::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .wasm-pdf-viewer ::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
        }
        .wasm-pdf-viewer ::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.3);
          border-radius: 4px;
        }
        .wasm-pdf-viewer ::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.5);
        }
      `}</style>
    </div>
  );
};

export default WasmPDFViewer;
