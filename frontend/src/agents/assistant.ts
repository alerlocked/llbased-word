/**
 * 主控Agent前端接口
 * 负责与Orchestrator的通信和状态管理
 */

import { api } from '../services/api';

export interface IntentRequest {
  user_input: string;
  user_id?: number;
  project_id?: number;
}

export interface AssistantResponse {
  status: 'success' | 'error';
  current_step: string;
  message: string;
  data?: any;
}

export class AssistantService {
  /**
   * 提交工艺意图
   */
  static async submitIntent(intent: IntentRequest): Promise<AssistantResponse> {
    try {
      const response = await api.post('/api/assistant/intent', intent);
      return response.data;
    } catch (error) {
      console.error('Failed to submit intent:', error);
      throw error;
    }
  }

  /**
   * 获取工艺建议
   */
  static async getSuggestions(sessionId: string): Promise<AssistantResponse> {
    try {
      const response = await api.get(`/api/assistant/suggestions?session_id=${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get suggestions:', error);
      throw error;
    }
  }

  /**
   * 生成工艺文档
   */
  static async generateDocument(intent: IntentRequest): Promise<AssistantResponse> {
    try {
      const response = await api.post('/api/assistant/generate', intent);
      return response.data;
    } catch (error) {
      console.error('Failed to generate document:', error);
      throw error;
    }
  }
}