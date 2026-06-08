/**
 * useSuggestions - 建议获取 Hook
 * 根据光标位置获取 AI 建议（防抖处理）
 */
import { useState, useCallback, useRef, useEffect } from 'react';

interface Suggestion {
  id: string;
  type: 'rewrite' | 'expand' | 'polish' | 'translate' | 'summarize' | 'extract';
  title: string;
  description: string;
  icon?: string;
}

interface UseSuggestionsOptions {
  debounceMs?: number;
  enabled?: boolean;
}

interface UseSuggestionsReturn {
  suggestions: Suggestion[];
  isLoading: boolean;
  error: string | null;
  fetchSuggestions: (context: string, selectedText?: string) => Promise<void>;
}

const API_BASE_URL = '/api/assistant';

// 默认建议列表（无网络时使用）
const DEFAULT_SUGGESTIONS: Suggestion[] = [
  {
    id: 'rewrite',
    type: 'rewrite',
    title: '重写',
    description: '用不同方式表达相同意思',
    icon: 'edit',
  },
  {
    id: 'expand',
    type: 'expand',
    title: '扩展',
    description: '添加更多细节和说明',
    icon: 'expand',
  },
  {
    id: 'polish',
    type: 'polish',
    title: '润色',
    description: '优化语言表达',
    icon: 'polish',
  },
  {
    id: 'translate',
    type: 'translate',
    title: '翻译',
    description: '翻译选中文本',
    icon: 'translate',
  },
  {
    id: 'summarize',
    type: 'summarize',
    title: '总结',
    description: '提炼核心要点',
    icon: 'summarize',
  },
  {
    id: 'extract',
    type: 'extract',
    title: '提取',
    description: '提取关键信息',
    icon: 'extract',
  },
];

export function useSuggestions(
  options: UseSuggestionsOptions = {}
): UseSuggestionsReturn {
  const { debounceMs = 300, enabled = true } = options;

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchSuggestions = useCallback(
    async (context: string, selectedText?: string) => {
      if (!enabled) {
        return;
      }

      // 取消之前的请求
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          context,
          cursor_position: String(context.length),
        });
        if (selectedText) {
          params.set('selected_text', selectedText);
        }
        const response = await fetch(`${API_BASE_URL}/suggestions?${params}`, {
          method: 'GET',
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.suggestions && Array.isArray(data.suggestions)) {
          setSuggestions(
            data.suggestions.map((s: any) => ({
              id: s.id || s.type,
              type: s.type,
              title: s.title,
              description: s.description,
              icon: s.icon,
            }))
          );
        } else {
          // 使用默认建议
          setSuggestions(DEFAULT_SUGGESTIONS);
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }

        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch suggestions';
        setError(errorMessage);
        
        // 网络错误时使用默认建议
        setSuggestions(DEFAULT_SUGGESTIONS);
      } finally {
        setIsLoading(false);
      }
    },
    [enabled]
  );

  // 防抖版本的 fetchSuggestions
  const debouncedFetchSuggestions = useCallback(
    (context: string, selectedText?: string): Promise<void> => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      debounceRef.current = setTimeout(() => {
        fetchSuggestions(context, selectedText);
      }, debounceMs);
      return Promise.resolve();
    },
    [fetchSuggestions, debounceMs]
  );

  // 清理
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    suggestions,
    isLoading,
    error,
    fetchSuggestions: debouncedFetchSuggestions,
  };
}
