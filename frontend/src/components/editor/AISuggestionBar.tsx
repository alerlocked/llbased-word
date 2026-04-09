/**
 * AISuggestionBar - AI 建议栏组件
 * 固定在编辑器底部，提供 AI 建议操作
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Editor } from '@tiptap/react';
import { Spin, Empty, Tooltip } from 'antd';
import { 
  RiMagicFill, 
  RiEditBoxLine, 
  RiFileTextLine, 
  RiTranslate2,
  RiListCheck,
  RiSparklingLine,
  RiArrowDownSLine,
  RiArrowUpSLine,
} from 'react-icons/ri';
import { useSuggestions } from '../../hooks/useSuggestions';
import styles from './AISuggestionBar.module.css';

interface AISuggestionBarProps {
  editor: Editor | null;
  onAction: (action: string) => void;
  visible?: boolean;
}

interface SuggestionItem {
  id: string;
  type: 'rewrite' | 'expand' | 'polish' | 'translate' | 'summarize' | 'extract';
  title: string;
  description: string;
  icon: React.ReactNode;
}

// ACTION_ICONS 定义（优化为 useMemo）
const getActionIcons = (): Record<string, React.ReactNode> => ({
  rewrite: <RiEditBoxLine />,
  expand: <RiFileTextLine />,
  polish: <RiSparklingLine />,
  translate: <RiTranslate2 />,
  summarize: <RiListCheck />,
  extract: <RiMagicFill />,
});

// 默认建议（优化为 useMemo）
const getDefaultSuggestions = (): SuggestionItem[] => [
  {
    id: 'continue',
    type: 'expand',
    title: '继续写作',
    description: '基于当前内容继续生成',
    icon: <RiMagicFill />,
  },
  {
    id: 'summarize',
    type: 'summarize',
    title: '生成摘要',
    description: '为当前段落生成摘要',
    icon: <RiListCheck />,
  },
  {
    id: 'polish',
    type: 'polish',
    title: '润色文本',
    description: '优化语言表达',
    icon: <RiSparklingLine />,
  },
  {
    id: 'translate',
    type: 'translate',
    title: '翻译',
    description: '翻译为英文',
    icon: <RiTranslate2 />,
  },
];

const AISuggestionBar: React.FC<AISuggestionBarProps> = ({
  editor,
  onAction,
  visible = true,
}) => {
  const [context, setContext] = useState<string>('');
  const [collapsed, setCollapsed] = useState<boolean>(false);
  
  // useMemo 优化常量
  const actionIcons = useMemo(() => getActionIcons(), []);
  const defaultSuggestions = useMemo(() => getDefaultSuggestions(), []);
  
  const { suggestions, isLoading, error, fetchSuggestions } = useSuggestions({
    debounceMs: 500,
    enabled: visible && !collapsed,
  });

  // 获取当前光标位置的上下文
  const getContext = useCallback(() => {
    if (!editor) return '';

    const { $from } = editor.state.selection;
    const start = Math.max(0, $from.pos - 200);
    const end = Math.min(editor.state.doc.content.size, $from.pos + 200);
    
    try {
      return editor.state.doc.textBetween(start, end);
    } catch (e) {
      return '';
    }
  }, [editor]);

  // 监听光标位置变化，更新上下文
  useEffect(() => {
    if (!editor || !visible || collapsed) return;

    const updateContext = () => {
      const newContext = getContext();
      setContext(newContext);
      
      if (newContext) {
        fetchSuggestions(newContext);
      }
    };

    // 初始化
    updateContext();

    // 监听光标变化
    editor.on('selectionUpdate', updateContext);

    return () => {
      editor.off('selectionUpdate', updateContext);
    };
  }, [editor, visible, collapsed, getContext, fetchSuggestions]);

  // useMemo 优化显示建议列表
  const displaySuggestions = useMemo(() => {
    if (suggestions.length > 0) {
      return suggestions.map(s => ({
        ...s,
        icon: actionIcons[s.type] || <RiMagicFill />,
      }));
    }
    return defaultSuggestions;
  }, [suggestions, actionIcons, defaultSuggestions]);

  if (!visible) {
    return null;
  }

  const handleSuggestionClick = (suggestion: SuggestionItem) => {
    onAction(suggestion.type);
  };

  const toggleCollapsed = () => {
    setCollapsed(!collapsed);
  };

  return (
    <div className={`${styles.suggestionBar} ${collapsed ? styles.collapsed : ''}`}>
      <div className={styles.header} onClick={toggleCollapsed}>
        <div className={styles.headerLeft}>
          <RiMagicFill className={styles.headerIcon} />
          <span className={styles.title}>AI 建议</span>
        </div>
        <button className={styles.toggleButton} aria-label={collapsed ? '展开' : '收起'} title={collapsed ? '展开建议栏' : '收起建议栏'}>
          {collapsed ? <RiArrowUpSLine /> : <RiArrowDownSLine />}
        </button>
      </div>
      
      {!collapsed && (
        <div className={styles.content}>
          {isLoading ? (
            <div className={styles.loading}>
              <Spin size="small" />
              <span>正在获取建议...</span>
            </div>
          ) : error ? (
            <div className={styles.error}>
              <span>获取建议失败，使用默认建议</span>
            </div>
          ) : (
            <div className={styles.suggestions}>
              {displaySuggestions.map((suggestion) => (
                <Tooltip
                  key={suggestion.id}
                  title={suggestion.description}
                  placement="top"
                >
                  <button
                    className={styles.suggestionItem}
                    onClick={() => handleSuggestionClick(suggestion)}
                    aria-label={suggestion.title}
                    title={suggestion.description}
                  >
                    <span className={styles.suggestionIcon}>{suggestion.icon}</span>
                    <span className={styles.suggestionTitle}>{suggestion.title}</span>
                  </button>
                </Tooltip>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AISuggestionBar;
