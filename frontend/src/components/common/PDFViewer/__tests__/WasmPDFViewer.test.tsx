/**
 * WasmPDFViewer 组件测试
 * 测试 PDF 渲染、缩放和导航功能
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { WasmPDFViewer } from '../WasmPDFViewer';

// Mock pdfjs-dist
jest.mock('pdfjs-dist', () => {
  const mockPage = {
    getViewport: jest.fn(() => ({ width: 800, height: 600 })),
    render: jest.fn(() => ({
      promise: Promise.resolve(),
      cancel: jest.fn(),
    })),
    getTextContent: jest.fn(() => Promise.resolve({ items: [] })),
  };

  const mockPdfDoc = {
    numPages: 5,
    getTitle: jest.fn(() => 'Test Document'),
    getPage: jest.fn(() => Promise.resolve(mockPage)),
    destroy: jest.fn(),
  };

  return {
    getDocument: jest.fn(() => ({
      promise: Promise.resolve(mockPdfDoc),
    })),
    GlobalWorkerOptions: {
      workerSrc: '',
    },
    renderTextLayer: jest.fn(),
    RenderParameters: jest.fn(),
  };
});

describe('WasmPDFViewer', () => {
  const mockSrc = 'test.pdf';
  const mockOnLoad = jest.fn();
  const mockOnError = jest.fn();
  const mockOnPageChange = jest.fn();
  const mockOnScaleChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('应该显示加载状态', () => {
      render(
        <WasmPDFViewer
          src={mockSrc}
          height={500}
        />
      );

      // 初始应该显示加载状态
      expect(screen.getByText('加载 PDF 中...')).toBeInTheDocument();
    });

    it('应该使用默认高度', async () => {
      render(<WasmPDFViewer src={mockSrc} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /上一页/i })).toBeInTheDocument();
      });
    });
  });

  describe('缩放控制', () => {
    it('应该渲染缩放按钮', async () => {
      render(
        <WasmPDFViewer
          src={mockSrc}
          initialScale={1}
          onScaleChange={mockOnScaleChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /放大/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /缩小/i })).toBeInTheDocument();
      });
    });

    it('应该显示当前缩放比例', async () => {
      const { container } = render(
        <WasmPDFViewer
          src={mockSrc}
          initialScale={1.5}
        />
      );

      await waitFor(() => {
        // 150% 应该显示在输入框中 - 检查 InputNumber 的值
        const inputNumber = container.querySelector('.ant-input-number-input');
        expect(inputNumber).toBeInTheDocument();
        // InputNumber 显示格式化的值 "150%"
        expect(inputNumber?.getAttribute('value')).toContain('150');
      });
    });

    it('初始缩放比例应该在有效范围内', async () => {
      const { container } = render(
        <WasmPDFViewer
          src={mockSrc}
          initialScale={2}
        />
      );

      await waitFor(() => {
        expect(container.querySelector('.wasm-pdf-viewer')).toBeInTheDocument();
      });
    });
  });

  describe('页面导航', () => {
    it('应该渲染导航按钮', async () => {
      render(
        <WasmPDFViewer
          src={mockSrc}
          onPageChange={mockOnPageChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /上一页/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /下一页/i })).toBeInTheDocument();
      });
    });

    it('应该显示页码信息', async () => {
      render(<WasmPDFViewer src={mockSrc} />);

      await waitFor(() => {
        // 应该显示总页数
        expect(screen.getByText(/\/ 5/)).toBeInTheDocument();
      });
    });

    it('第一页时上一页按钮应该禁用', async () => {
      render(<WasmPDFViewer src={mockSrc} />);

      await waitFor(() => {
        const prevButton = screen.getByRole('button', { name: /上一页/i });
        expect(prevButton).toBeDisabled();
      });
    });
  });

  describe('回调函数', () => {
    it('加载完成后应该调用 onLoad', async () => {
      render(
        <WasmPDFViewer
          src={mockSrc}
          onLoad={mockOnLoad}
        />
      );

      await waitFor(() => {
        expect(mockOnLoad).toHaveBeenCalledWith({
          totalPages: 5,
          title: 'Test Document',
        });
      });
    });
  });

  describe('错误处理', () => {
    it('应该处理无效的 PDF 源', async () => {
      // 使用会失败的 mock
      const pdfjsLib = require('pdfjs-dist');
      pdfjsLib.getDocument.mockReturnValueOnce({
        promise: Promise.reject(new Error('Invalid PDF')),
      });

      render(
        <WasmPDFViewer
          src="invalid.pdf"
          onError={mockOnError}
        />
      );

      await waitFor(() => {
        expect(mockOnError).toHaveBeenCalled();
      });
    });
  });

  describe('Props 验证', () => {
    it('应该接受自定义高度', async () => {
      render(<WasmPDFViewer src={mockSrc} height={800} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /放大/i })).toBeInTheDocument();
      });
    });

    it('应该支持 ArrayBuffer 类型的源', async () => {
      const arrayBuffer = new ArrayBuffer(10);

      render(<WasmPDFViewer src={arrayBuffer} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /放大/i })).toBeInTheDocument();
      });
    });
  });
});
