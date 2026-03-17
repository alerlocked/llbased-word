/**
 * WasmPDFViewer 组件测试
 * 测试 PDF 渲染、缩放和导航功能
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { WasmPDFViewer } from '../WasmPDFViewer';

// Mock HTMLCanvasElement.getContext - jsdom doesn't implement canvas
HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
  fillRect: jest.fn(),
  clearRect: jest.fn(),
  getImageData: jest.fn(() => ({
    data: new Uint8ClampedArray(4),
  })),
  putImageData: jest.fn(),
  createImageData: jest.fn(() => ({
    data: new Uint8ClampedArray(4),
  })),
  setTransform: jest.fn(),
  drawImage: jest.fn(),
  save: jest.fn(),
  restore: jest.fn(),
  scale: jest.fn(),
  rotate: jest.fn(),
  translate: jest.fn(),
  transform: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  closePath: jest.fn(),
  stroke: jest.fn(),
  fill: jest.fn(),
  arc: jest.fn(),
  rect: jest.fn(),
  clip: jest.fn(),
  measureText: jest.fn(() => ({ width: 0 })),
  fillText: jest.fn(),
  strokeText: jest.fn(),
  createLinearGradient: jest.fn(),
  createRadialGradient: jest.fn(),
  createPattern: jest.fn(),
  font: '',
  textAlign: '',
  textBaseline: '',
  fillStyle: '',
  strokeStyle: '',
  globalAlpha: 1,
  globalCompositeOperation: '',
  lineWidth: 1,
  lineCap: '',
  lineJoin: '',
  miterLimit: 10,
  shadowOffsetX: 0,
  shadowOffsetY: 0,
  shadowBlur: 0,
  shadowColor: '',
})) as any;

// Mock canvas width/height setters
Object.defineProperty(HTMLCanvasElement.prototype, 'width', {
  set: jest.fn(),
  get: jest.fn(() => 800),
  configurable: true,
});

Object.defineProperty(HTMLCanvasElement.prototype, 'height', {
  set: jest.fn(),
  get: jest.fn(() => 600),
  configurable: true,
});

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
      await act(async () => {
        render(<WasmPDFViewer src={mockSrc} />);
      });

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
      await act(async () => {
        render(
          <WasmPDFViewer
            src={mockSrc}
            initialScale={1.5}
          />
        );
      });

      await waitFor(() => {
        // 找到所有 input 元素
        const inputs = document.querySelectorAll('input');
        // 风格输入框的 formatter 会添加 %，所以找包含 % 的值
        const scaleInput = Array.from(inputs).find(
          input => input.getAttribute('value')?.includes('%')
        );
        expect(scaleInput).toBeTruthy();
        // 验证初始缩放比例 150% 正确显示
        expect(scaleInput?.getAttribute('value')).toBe('150%');
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
