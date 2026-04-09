/**
 * AIContextMenu - 选区快捷菜单组件
 * 选中文字时显示 AI 操作菜单
 */
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Editor } from '@tiptap/react';
import { Spin, Button, Tooltip } from 'antd';
import {
  RiEdit2Line,
  RiFileAddLine,
  RiSparklingLine,
  RiTranslate2,
  RiFileListLine,
  RiFilterLine,
  RiCheckLine,
  RiCloseLine,
  RiRefreshLine,
} from 'react-icons/ri';
import { useAIStream } from '../../hooks/useAIStream';
import type { SelectionInfo, Position } from '../../hooks/useSelection';
import { replaceWithFormatPreservation } from '../../utils/formatPreservation';
import styles from './AIContextMenu.module.css';

type AIAction = 'rewrite' | 'expand' | 'polish' | 'translate' | 'summarize' | 'extract' | 'illustrate';

interface AIContextMenuProps {
  editor: Editor | null;
  selection: SelectionInfo | null;
  position: Position | null;
  visible: boolean;
  onClose: () => void;
  onOpenImageDialog?: () => void;
}

interface ActionItem {
  id: AIAction;
  title: string;
  description: string;
  icon: React.ReactNode;
}

// 使用 useMemo 优化的 ACTIONS 定义（在组件外定义）
const getActions = (): ActionItem[] => [
  {
    id: 'rewrite',
    title: '重写',
    description: '用不同方式表达相同内容',
    icon: <RiEdit2Line />,
  },
  {
    id: 'expand',
    title: '扩展',
    description: '添加更多细节和内容',
    icon: <RiFileAddLine />,
  },
  {
    id: 'polish',
    title: '润色',
    description: '优化语言表达和文风',
    icon: <RiSparklingLine />,
  },
  {
    id: 'translate',
    title: '翻译',
    description: '翻译为英文',
    icon: <RiTranslate2 />,
  },
  {
    id: 'summarize',
    title: '总结',
    description: '提炼核心要点',
    icon: <RiFileListLine />,
  },
  {
    id: 'extract',
    title: '提取',
    description: '提取关键信息',
    icon: <RiFilterLine />,
  },
  {
    id: 'illustrate',
    title: '插图',
    description: '在光标位置插入图片',
    icon: <span style={{ fontSize: 16 }}>🖼️</span>,
  },
];

const AIContextMenu: React.FC<AIContextMenuProps> = ({
  editor,
  selection,
  position,
  visible,
  onClose,
  onOpenImageDialog,
}) => {
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const [previewContent, setPreviewContent] = useState<string>('');
  
  const menuRef = useRef<HTMLDivElement>(null);
  
  // useMemo 优化 ACTIONS
  const actions = useMemo(() => getActions(), []);

  const {
    state: streamState,
    content: streamContent,
    error: streamError,
    retryCount,
    startStream,
    cancelStream,
    retry,
  } = useAIStream({
    maxRetries: 3,
    retryDelay: 1000,
    onComplete: (content) => {
      setPreviewContent(content);
    },
    onError: (error) => {
      console.error('Stream error:', error);
    },
  });

  // 计算菜单位置
  useEffect(() => {
    if (!position || !visible) return;

    const menuWidth = 240;
    const menuHeight = 40;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let left = position.left - menuWidth / 2;
    let top = position.top - menuHeight - 10;

    // 确保不超出视口边界
    if (left < 10) left = 10;
    if (left + menuWidth > viewportWidth - 10) left = viewportWidth - menuWidth - 10;
    if (top < 10) top = position.bottom + 10;

    setMenuPosition({ top, left });
  }, [position, visible]);

  // 处理点击外部关闭菜单
  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [visible, onClose]);

  // 处理 AI 操作
  const handleAction = useCallback(
    (action: AIAction) => {
      if (action === 'illustrate') {
        // 插图操作：调用外部图片对话框
        onOpenImageDialog?.();
        onClose();
        return;
      }

      if (!selection?.text) return;

      setPreviewContent('');
      startStream(action, selection.text);
    },
    [selection, startStream, onOpenImageDialog, onClose]
  );

  // 接受生成的内容（带格式保留）
  const handleAccept = useCallback(() => {
    if (!editor || !selection || !previewContent) return;

    // 使用格式保留替换
    replaceWithFormatPreservation(
      editor,
      selection.from,
      selection.to,
      previewContent
    );

    onClose();
  }, [editor, selection, previewContent, onClose]);

  // 拒绝生成的内容
  const handleReject = useCallback(() => {
    setPreviewContent('');
    cancelStream();
  }, [cancelStream]);

  if (!visible || !selection?.text) {
    return null;
  }

  const isStreaming = streamState === 'streaming';
  const hasError = streamState === 'error';
  const hasContent = previewContent || streamContent;

  return (
    <div
      ref={menuRef}
      className={`${styles.menu} ${isStreaming ? styles.menuStreaming : ''} ${hasError ? styles.menuError : ''}`}
      style={{
        top: menuPosition.top,
        left: menuPosition.left,
      }}
    >
      {/* 操作按钮列表 */}
      {!isStreaming && !hasContent && (
        <>
          {actions.map((action) => (
            <Tooltip
              key={action.id}
              title={action.description}
              placement="top"
            >
              <button
                className={styles.menuItem}
                onClick={() => handleAction(action.id)}
                aria-label={action.title}
                title={action.description}
              >
                <span className={styles.menuItemIcon}>{action.icon}</span>
                <div className={styles.menuItemContent}>
                  <div className={styles.menuItemTitle}>{action.title}</div>
                </div>
              </button>
            </Tooltip>
          ))}
        </>
      )}

      {/* 流式生成中 */}
      {isStreaming && !previewContent && (
        <div className={styles.streamingIndicator}>
          <div className={styles.streamingDots}>
            <span className={styles.streamingDot} />
            <span className={styles.streamingDot} />
            <span className={styles.streamingDot} />
          </div>
          <span className={styles.streamingText}>
            AI 正在生成...
            {retryCount > 0 && <span> (重试 {retryCount}/3)</span>}
          </span>
        </div>
      )}

      {/* 预览内容 */}
      {hasContent && (
        <div className={styles.previewContainer}>
          <div className={styles.previewLabel}>预览</div>
          <div className={styles.previewContent}>
            {previewContent || streamContent}
          </div>
          <div className={styles.actionButtons}>
            <Button
              type="primary"
              size="small"
              icon={<RiCheckLine />}
              onClick={handleAccept}
              disabled={isStreaming}
            >
              接受
            </Button>
            <Button
              size="small"
              icon={<RiCloseLine />}
              onClick={handleReject}
            >
              拒绝
            </Button>
          </div>
        </div>
      )}

      {/* 错误状态 */}
      {hasError && (
        <div className={styles.errorContent}>
          <div className={styles.errorMessage}>
            {streamError}
            {retryCount >= 3 && ' (已达最大重试次数)'}
          </div>
          {retryCount < 3 && (
            <button className={styles.retryButton} onClick={retry} aria-label="重试" title="重试">
              <RiRefreshLine /> 重试
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default AIContextMenu;
