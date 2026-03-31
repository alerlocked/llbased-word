/**
 * useAIStream - 流式生成 Hook
 * 处理 SSE 流式生成，支持取消、重试
 */
import { useState, useCallback, useRef } from 'react';

export type StreamingState = 'idle' | 'streaming' | 'error' | 'done';

interface UseAIStreamOptions {
  onError?: (error: string) => void;
  onComplete?: (content: string) => void;
  onChunk?: (chunk: string) => void;
}

interface UseAIStreamReturn {
  state: StreamingState;
  content: string;
  error: string | null;
  startStream: (action: string, selectedText: string, context?: string) => Promise<void>;
  cancelStream: () => void;
  retry: () => void;
}

const API_BASE_URL = '/api/assistant';

export function useAIStream(options: UseAIStreamOptions = {}): UseAIStreamReturn {
  const { onError, onComplete, onChunk } = options;
  
  const [state, setState] = useState<StreamingState>('idle');
  const [content, setContent] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastRequestRef = useRef<{ action: string; selectedText: string; context?: string } | null>(null);

  const startStream = useCallback(async (
    action: string,
    selectedText: string,
    context?: string
  ) => {
    // 取消之前的流
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 创建新的 AbortController
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // 保存请求参数用于重试
    lastRequestRef.current = { action, selectedText, context };

    setState('streaming');
    setContent('');
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/quick-actions`, {
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
                accumulatedContent += data.content;
                setContent(accumulatedContent);
                onChunk?.(data.content);
              }

              if (data.done) {
                setState('done');
                onComplete?.(accumulatedContent);
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }

      // 如果流结束但未收到 done 信号
      if (state !== 'done') {
        setState('done');
        onComplete?.(accumulatedContent);
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
    }
  }, [onError, onComplete, onChunk, state]);

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState('idle');
    setContent('');
    setError(null);
  }, []);

  const retry = useCallback(() => {
    if (lastRequestRef.current) {
      const { action, selectedText, context } = lastRequestRef.current;
      startStream(action, selectedText, context);
    }
  }, [startStream]);

  return {
    state,
    content,
    error,
    startStream,
    cancelStream,
    retry,
  };
}
