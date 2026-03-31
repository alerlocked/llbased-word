/**
 * aiService - AI 服务封装
 * 封装后端 AI API 调用
 */

const API_BASE_URL = '/api/assistant';

export type AIAction = 'rewrite' | 'expand' | 'polish' | 'translate' | 'summarize' | 'extract';

export interface QuickActionRequest {
  action: AIAction;
  selected_text: string;
  context?: string;
  stream?: boolean;
}

export interface QuickActionResponse {
  content: string;
  word_count: number;
  action: AIAction;
}

export interface SuggestionRequest {
  context: string;
  selected_text?: string;
  cursor_position?: number;
  document_type?: string;
}

export interface Suggestion {
  id: string;
  type: AIAction;
  title: string;
  description: string;
  preview?: string;
}

export interface SuggestionsResponse {
  suggestions: Suggestion[];
  context_analysis?: string;
}

/**
 * 获取 AI 建议
 */
export async function getSuggestions(request: SuggestionRequest): Promise<SuggestionsResponse> {
  const response = await fetch(`${API_BASE_URL}/suggestions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

/**
 * 执行快捷 AI 操作（非流式）
 */
export async function executeQuickAction(request: QuickActionRequest): Promise<QuickActionResponse> {
  const response = await fetch(`${API_BASE_URL}/quick-actions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...request,
      stream: false,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

/**
 * 执行快捷 AI 操作（流式）
 * 返回 ReadableStream 用于处理 SSE
 */
export async function executeQuickActionStream(
  request: QuickActionRequest,
  onChunk: (chunk: string) => void,
  onError: (error: string) => void,
  onComplete: () => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/quick-actions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({
      ...request,
      stream: true,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No reader available');
  }

  const decoder = new TextDecoder();

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
            onError(data.error);
            return;
          }

          if (data.content) {
            onChunk(data.content);
          }

          if (data.done) {
            onComplete();
            return;
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }

  onComplete();
}

export default {
  getSuggestions,
  executeQuickAction,
  executeQuickActionStream,
};
