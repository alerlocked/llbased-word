import React, { useState, useEffect, useCallback } from 'react';
import { Editor } from '@tiptap/react';
import { Spin, Empty } from 'antd';
import { 
  RiMagicFill, 
  RiEditBoxLine, 
  RiFileTextLine, 
  RiTranslate2,
  RiListCheck,
  RiSparklingLine
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

const ACTION_ICONS: Record<string, React.ReactNode> = {
  rewrite: <RiEditBoxLine />,
  expand: <RiFileTextLine />,
  polish: <RiSparklingLine />,
  translate: <RiTranslate2 />,
  summarize: <RiListCheck />,
  extract: <RiMagicFill />,
};

const DEFAULT_SUGGESTIONS: SuggestionItem[] = [
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
  
  const { suggestions, isLoading, error, fetchSuggestions } = useSuggestions({
    debounceMs: 500,
    enabled: visible,
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
    if (!editor || !visible) return;

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
  }, [editor, visible, getContext, fetchSuggestions]);

  // 显示的建议列表
  const displaySuggestions = suggestions.length > 0 
    ? suggestions.map(s => ({
        ...s,
        icon: ACTION_ICONS[s.type] || <RiMagicFill />,
      }))
    : DEFAULT_SUGGESTIONS;

  if (!visible) {
    return null;
  }

  const handleSuggestionClick = (suggestion: SuggestionItem) => {
    onAction(suggestion.type);
  };

  return (
    <div className={styles.suggestionBar}>
      <div className={styles.header}>
        <RiMagicFill className={styles.headerIcon} />
        <span className={styles.title}>AI 建议</span>
      </div>
      
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
              <button
                key={suggestion.id}
                className={styles.suggestionItem}
                onClick={() => handleSuggestionClick(suggestion)}
                title={suggestion.description}
              >
                <span className={styles.suggestionIcon}>{suggestion.icon}</span>
                <span className={styles.suggestionTitle}>{suggestion.title}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AISuggestionBar;
