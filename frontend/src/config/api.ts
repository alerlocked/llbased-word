/**
 * API配置 - 集中管理API端点
 * 避免在代码中硬编码API URL
 */

// 环境变量配置
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.REACT_APP_API_VERSION || 'v1';

// API端点配置
export const API_ENDPOINTS = {
  // 基础URL
  BASE: `${API_BASE_URL}/api/${API_VERSION}`,

  // 项目相关
  PROJECTS: {
    LIST: '/projects/list',
    CREATE: '/projects/create',
    UPDATE: '/projects/update',
    DELETE: '/projects/delete',
    GET: '/projects/get',
    ADD_MATERIAL: '/projects/add-material',
    REMOVE_MATERIAL: '/projects/remove-material',
  },

  // 创作相关
  CREATION: {
    GET: '/creation/get',
    UPDATE: '/creation/update',
    SAVE: '/creation/save',
    PUBLISH: '/creation/publish',
  },

  // 文章相关
  ARTICLES: {
    LIST: '/articles/list',
    GET: '/articles/get',
    UPDATE: '/articles/update',
    DELETE: '/articles/delete',
    EXPORT: '/articles/export',
  },

  // AI Agent相关
  AGENT: {
    CHAT: '/agent/chat',
    CREATE: '/agent/create',
    STATUS: '/agent/status',
    STREAM: '/agent/stream',
  },

  // 风格学习相关
  STYLE: {
    ANALYZE: '/style/analyze',
    APPLY: '/style/apply',
    LEARN: '/style/learn',
    PROFILE: '/style/profile',
  },

  // 工具相关
  TOOLS: {
    SEARCH: '/tools/search',
    RAG_SEARCH: '/tools/rag-search',
    WEB_SEARCH: '/tools/web-search',
  },

  // 系统相关
  SYSTEM: {
    HEALTH: '/health',
    STATUS: '/status',
    CONFIG: '/config',
  },

  // 工艺文档处理相关
  PROCESS_DOCUMENTS: {
    LIST: '/process-documents/',
    EXTRACTED: '/process-documents/{doc_id}/extracted',
    VIEW: '/process-documents/{doc_id}/view',
    SUMMARY: '/process-documents/{doc_id}/summary',
    TABLES: '/process-documents/{doc_id}/tables/{type}',
    TOOLS: '/process-documents/{doc_id}/tools',
    EXTRACT: '/process-documents/{doc_id}/extract',
    DELETE_EXTRACTED: '/process-documents/{doc_id}/extracted',
  },
};

// 构建完整URL的工具函数
export const buildApiUrl = (endpoint: string): string => {
  return `${API_ENDPOINTS.BASE}${endpoint}`;
};

// WebSocket端点
export const WS_ENDPOINTS = {
  BASE: API_BASE_URL.replace('http', 'ws'),
  AGENT_STREAM: '/ws/agent/stream',
};

// 配置检查
export const validateApiConfig = (): boolean => {
  if (!API_BASE_URL) {
    console.error('API_BASE_URL is not configured');
    return false;
  }
  return true;
};