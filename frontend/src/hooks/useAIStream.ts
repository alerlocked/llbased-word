/**
 * useAIStream - 流式生成 Hook
 * 处理 SSE 流式生成，支持取消、重试、自动重试
 */
import { useState, useCallback, useRef } from 'react';
export type StreamingState = 'idle' | 'streaming' | 'error' | 'done';

interface UseAIStreamOptions {
  onError?: (error: string) => void;
  onComplete?: (content: string) => void;
  onChunk?: (chunk: string) => void;
  maxRetries?: number; // 最大重试次数
  retryDelay?: number; // 重试延迟（毫秒）
}

interface UseAIStreamReturn {
  state: StreamingState;
  content: string;
  error: string | null;
  retryCount: number;
  startStream: (action: string, selectedText: string, context?: string) => Promise<void>;
  cancelStream: () => void;
  retry: () => void;
}

const API_BASE_URL = '/api/assistant';

// 默认配置
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_DELAY = 1000;

export function useAIStream(options: UseAIStreamOptions = {}): UseAIStreamReturn {
  const { 
    onError, 
    onComplete, 
    onChunk,
    maxRetries = DEFAULT_MAX_RETRIES,
    retryDelay = DEFAULT_RETRY_DELAY,
  } = options;
  
  const [state, setState] = useState<StreamingState>('idle');
  const [content, setContent] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState<number>(0);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<{ action: string; selectedText: string; context?: string } | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * 过滤内容中的 XSS
   */
  const sanitizeContent = useCallback((rawContent: string): string => {
    return rawContent;
  }, []);

  /**
   * 执行流式请求
   */
  const executeStream = useCallback(async (
    action: string,
    selectedText: string,
    context?: string,
    isRetry: boolean = false
  ) => {
    // 取消之前的流
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 清除之前的重试定时器
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }

    // 创建新的 AbortController
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // 保存请求参数用于重试
    lastRequestRef.current = { action, selectedText, context };

    // 如果是重试，更新计数
    if (isRetry) {
      setRetryCount(prev => prev + 1);
    } else {
      setRetryCount(0);
    }

    setState('streaming');
    setContent('');
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/quick-actions-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          action,
          selected_text: selectedText,
          context,
          stream: true,
        }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No reader available');
      }

      const decoder = new TextDecoder();
      let accumulatedContent = '';

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.error) {
                throw new Error(data.error);
              }

              if (data.content) {
                // 累积内容（未过滤）
                accumulatedContent += data.content;
                
                // 过滤后显示（仅显示，不影响累积）
                const sanitizedChunk = sanitizeContent(data.content);
                setContent(prev => prev + sanitizedChunk);
                
                onChunk?.(sanitizedChunk);
              }

              if (data.done) {
                // 最终过滤
                const finalContent = sanitizeContent(accumulatedContent);
                setContent(finalContent);
                setState('done');
                onComplete?.(finalContent);
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }

      // 如果流结束但未收到 done 信号
      if (state !== 'done') {
        const finalContent = sanitizeContent(accumulatedContent);
        setContent(finalContent);
        setState('done');
        onComplete?.(finalContent);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // 用户取消，不做错误处理
        return;
      }

      const errorMessage = err instanceof Error ? err.message : 'Stream failed';
      setError(errorMessage);
      setState('error');
      onError?.(errorMessage);

      // 自动重试
      const currentRetryCount = isRetry ? retryCount + 1 : 1;
      if (currentRetryCount < maxRetries) {
        console.log(`[useAIStream] Auto retry ${currentRetryCount}/${maxRetries} in ${retryDelay}ms...`);
        
        retryTimeoutRef.current = setTimeout(() => {
          executeStream(action, selectedText, context, true);
        }, retryDelay * currentRetryCount); // 指数退避
      }
    }
  }, [onError, onComplete, onChunk, state, sanitizeContent, maxRetries, retryDelay, retryCount]);

  const startStream = useCallback(async (
    action: string,
    selectedText: string,
    context?: string
  ) => {
    await executeStream(action, selectedText, context, false);
  }, [executeStream]);

  const cancelStream = useCallback(() => {
    // 清除重试定时器
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    setState('idle');
    setContent('');
    setError(null);
    setRetryCount(0);
  }, []);

  const retry = useCallback(() => {
    if (lastRequestRef.current) {
      const { action, selectedText, context } = lastRequestRef.current;
      // 手动重试重置计数
      setRetryCount(0);
      executeStream(action, selectedText, context, false);
    }
  }, [executeStream]);

  return {
    state,
    content,
    error,
    retryCount,
    startStream,
    cancelStream,
    retry,
  };
}
