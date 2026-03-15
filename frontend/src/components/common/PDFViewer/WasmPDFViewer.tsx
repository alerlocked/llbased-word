/**
 * WasmPDFViewer - WebAssembly PDF 预览组件
 * 基于 pdfjs-dist 实现高性能 PDF 渲染
 */
import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Button, Space, Slider, InputNumber, Spin, message, Tooltip } from 'antd';
import {
  ZoomInOutlined,
  ZoomOutOutlined,
  LeftOutlined,
  RightOutlined,
  FullscreenOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import * as pdfjsLib from 'pdfjs-dist';

// 设置 WebAssembly worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

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
}

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

        const title = pdfDoc.getTitle() || 'Untitled';

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
      // 取消正在进行的渲染任务
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [src, onLoad, onError]);

  // 渲染当前页面
  const renderPage = useCallback(async (pageNum: number, scale: number, rotation: number) => {
    const { pdfDoc } = state;
    if (!pdfDoc || !canvasRef.current || !textLayerRef.current) return;

    // 取消之前的渲染任务
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

      // 设置 canvas 尺寸
      canvas.height = viewport.height;
      canvas.width = viewport.width;

      // 渲染 PDF 页面
      const renderContext: pdfjsLib.RenderParameters = {
        canvasContext: context,
        viewport,
      };

      renderTaskRef.current = page.render(renderContext);
      await renderTaskRef.current.promise;
      renderTaskRef.current = null;

      // 渲染文本层（用于文本选择）
      const textLayer = textLayerRef.current;
      textLayer.innerHTML = '';
      textLayer.style.width = `${viewport.width}px`;
      textLayer.style.height = `${viewport.height}px`;

      const textContent = await page.getTextContent();

      // 使用 pdfjs-dist 的文本层渲染
      pdfjsLib.renderTextLayer({
        textContentSource: textContent,
        container: textLayer,
        viewport,
        textDivs: [],
      });
    } catch (err) {
      // 忽略取消错误
      if ((err as Error).name !== 'RenderingCancelledException') {
        console.error('页面渲染错误:', err);
      }
    }
  }, [state]);

  // 页面/缩放/旋转变化时重新渲染
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

  // 缩放百分比显示
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
          background: '#fafafa',
          borderRadius: 8,
        }}
      >
        <Spin size="large" tip="加载 PDF 中..." />
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
          background: '#fff2f0',
          borderRadius: 8,
          border: '1px solid #ffccc7',
          padding: 24,
        }}
      >
        <ReloadOutlined style={{ fontSize: 32, color: '#ff4d4f', marginBottom: 16 }} />
        <p style={{ color: '#ff4d4f', margin: 0 }}>PDF 加载失败</p>
        <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>{state.error}</p>
      </div>
    );
  }

  return (
    <div className="wasm-pdf-viewer" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 工具栏 */}
      <div
        style={{
          padding: '8px 16px',
          background: '#fff',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        {/* 页面导航 */}
        <Space>
          <Tooltip title="上一页">
            <Button
              icon={<LeftOutlined />}
              onClick={prevPage}
              disabled={state.currentPage <= 1}
            />
          </Tooltip>

          <Space.Compact>
            <InputNumber
              min={1}
              max={state.totalPages}
              value={state.currentPage}
              onChange={(val) => val && goToPage(val)}
              style={{ width: 60 }}
            />
            <Button disabled>/ {state.totalPages}</Button>
          </Space.Compact>

          <Tooltip title="下一页">
            <Button
              icon={<RightOutlined />}
              onClick={nextPage}
              disabled={state.currentPage >= state.totalPages}
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
          />

          <Tooltip title="放大">
            <Button
              icon={<ZoomInOutlined />}
              onClick={zoomIn}
              disabled={state.scale >= ZOOM_MAX}
            />
          </Tooltip>
        </Space>

        {/* 其他操作 */}
        <Space>
          <Tooltip title="旋转">
            <Button icon={<FullscreenOutlined />} onClick={rotate} />
          </Tooltip>
        </Space>
      </div>

      {/* PDF 内容区域 */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          background: '#525659',
          padding: 16,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <div style={{ position: 'relative' }}>
          <canvas
            ref={canvasRef}
            style={{
              display: 'block',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            }}
          />
          {/* 文本层 - 用于文本选择 */}
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

      {/* 样式：文本层选择效果 */}
      <style>{`
        .textLayer {
          user-select: text;
        }
        .textLayer ::selection {
          background: rgba(0, 0, 255, 0.3);
        }
        .textLayer span {
          color: transparent;
          position: absolute;
          white-space: pre;
          cursor: text;
          transform-origin: 0 0;
        }
      `}</style>
    </div>
  );
};

export default WasmPDFViewer;
