/**
 * 风格管理服务
 * 封装风格学习和管理相关的API调用
 */

import apiClient from './apiClient'

// 类型定义
export interface StyleProfile {
  id: number
  user_id: number
  scenario_name?: string
  reference_texts: string[]
  style_features: Record<string, any>
  confidence_score: number
  created_at: string
  updated_at: string
}

// 风格文章类型定义
export interface StyleArticle {
  id: number
  user_id: number
  title: string
  content: string
  source: string
  source_id: number | null
  is_trained: boolean
  word_count: number
  created_at: string
  updated_at: string
}

export interface StyleStatistics {
  total_count: number
  trained_count: number
  untrained_count: number
  source_breakdown: {
    upload: number
    agent_generated: number
    editor_saved: number
  }
  total_words: number
}

/**
 * 上传风格文章文件
 */
export async function uploadStyleArticle(
  file: File,
  userId: number
): Promise<{
  id: number
  title: string
  word_count: number
  source: string
  is_trained: boolean
  created_at: string
}> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await apiClient.post(`/style/articles/upload?user_id=${userId}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return response.data
}

/**
 * 获取风格文章列表
 */
export async function getStyleArticles(params: {
  user_id: number
  skip?: number
  limit?: number
  source?: string
  is_trained?: boolean
}): Promise<StyleArticle[]> {
  const response = await apiClient.get('/style/articles', { params })
  return response.data
}

/**
 * 删除风格文章
 */
export async function deleteStyleArticle(articleId: number): Promise<{
  message: string
  deleted_id: number
}> {
  const response = await apiClient.delete(`/style/articles/${articleId}`)
  return response.data
}

/**
 * 获取风格统计信息
 */
export async function getStyleStatistics(userId: number): Promise<StyleStatistics> {
  const response = await apiClient.get(`/style/statistics/${userId}`)
  return response.data
}

/**
 * 训练风格模型
 */
export async function trainStyleModel(userId: number): Promise<{
  message: string
  style_profile_id?: number
  trained_count: number
  confidence_score: number
}> {
  const response = await apiClient.post('/style/train', { user_id: userId })
  return response.data
}

/**
 * 从参考文本学习风格
 */
export async function learnFromReferences(params: {
  reference_texts: string[]
  user_id: number
  scenario_name?: string
  team_id?: number
}): Promise<{
  style_profile_id: number
  style_features: Record<string, any>
  confidence_score: number
}> {
  const response = await apiClient.post('/style/learn-from-references', params)
  return response.data
}

/**
 * 获取用户的风格档案列表
 */
export async function getStyleProfiles(userId: number): Promise<StyleProfile[]> {
  const response = await apiClient.get('/style/profiles', {
    params: { user_id: userId }
  })
  return response.data
}

/**
 * 获取单个风格档案
 */
export async function getStyleProfile(profileId: number): Promise<StyleProfile> {
  const response = await apiClient.get(`/style/profiles/${profileId}`)
  return response.data
}

/**
 * 更新风格档案
 */
export async function updateStyleProfile(
  profileId: number,
  params: {
    scenario_name?: string
    reference_texts?: string[]
    style_features?: Record<string, any>
  }
): Promise<StyleProfile> {
  const response = await apiClient.put(`/style/profiles/${profileId}`, params)
  return response.data
}

/**
 * 删除风格档案
 */
export async function deleteStyleProfile(profileId: number): Promise<{
  message: string
  deleted_id: number
}> {
  const response = await apiClient.delete(`/style/profiles/${profileId}`)
  return response.data
}

// ========== 画像管理API ==========

/**
 * StylePortrait类型定义（六维画像）
 */
export interface StylePortrait {
  style_overview: {
    summary: string
    tags: string[]
    formality_constraint: Record<string, any>
    paragraph_constraint: Record<string, any>
  }
  methodology: {
    approach: string
    analogy_rule: Record<string, any>
    structure_template?: string
    mandatory_patterns: string[]
  }
  thinking_core: {
    values: string[]
    value_judgment_function: Record<string, any>
    logic_patterns: string[]
    argumentation_rules: Record<string, any>
  }
  expression_features: {
    sentence_length_ratio: Record<string, number>
    sentence_constraints: Record<string, any>
    opening_habits: string[]
    keywords: string[]
    formality_level: string
  }
  writing_habits: {
    opening_phrases: string[]
    opening_rule: Record<string, any>
    transition_patterns: string[]
    closing_patterns: string[]
    paragraph_length_preference?: string
  }
  unique_markers: {
    background?: string
    expertise: string[]
    identity_framework: Record<string, any>
    perspective_rules: string[]
  }
  version: number
  confidence_score: number
  last_updated?: string
  source: 'auto' | 'manual' | 'hybrid'
}

/**
 * 画像列表项
 */
export interface PortraitListItem {
  id: number
  scenario_name?: string
  version: number
  confidence_score: number
  source: string
  last_updated?: string
  summary: string
}

/**
 * 上传文档并自动生成画像
 */
export async function uploadDocumentsAndGeneratePortrait(
  files: File[],
  userId: number,
  scenarioName?: string
): Promise<{
  portrait_id: number
  portrait: StylePortrait
  confidence_score: number
  version: number
  source: string
  valid_documents: number
  failed_files?: Array<{ filename: string; reason: string }>
}> {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  
  const params = new URLSearchParams()
  params.append('user_id', userId.toString())
  if (scenarioName) {
    params.append('scenario_name', scenarioName)
  }
  
  const response = await apiClient.post(
    `/style/portraits/upload-and-analyze?${params.toString()}`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 300000 // 5分钟超时（生成画像可能需要较长时间）
    }
  )
  return response.data
}

/**
 * 获取画像列表
 */
export async function getPortraitList(
  userId: number,
  scenarioName?: string
): Promise<{
  portraits: PortraitListItem[]
  total: number
}> {
  const params: any = { user_id: userId }
  if (scenarioName) {
    params.scenario_name = scenarioName
  }
  const response = await apiClient.get('/style/portraits', { params })
  return response.data
}

/**
 * 获取单个画像
 */
export async function getPortrait(portraitId: number): Promise<StylePortrait> {
  const response = await apiClient.get(`/style/portraits/${portraitId}`)
  return response.data
}

/**
 * 创建画像（手动创建）
 */
export async function createPortrait(
  portrait: StylePortrait,
  userId: number
): Promise<{
  id: number
  portrait: StylePortrait
  version: number
  confidence_score: number
  source: string
}> {
  const response = await apiClient.post(`/style/portraits?user_id=${userId}`, portrait)
  return response.data
}

/**
 * 更新画像
 */
export async function updatePortrait(
  portraitId: number,
  portrait: StylePortrait
): Promise<{
  id: number
  portrait: StylePortrait
  version: number
  confidence_score: number
}> {
  const response = await apiClient.put(`/style/portraits/${portraitId}`, portrait)
  return response.data
}

/**
 * 合并画像
 */
export async function mergePortrait(
  portraitId: number,
  autoGenerated: StylePortrait,
  mergeMode: 'smart' | 'auto' | 'manual' = 'smart'
): Promise<{
  id: number
  portrait: StylePortrait
  version: number
  merge_mode: string
}> {
  const response = await apiClient.post(
    `/style/portraits/${portraitId}/merge?merge_mode=${mergeMode}`,
    autoGenerated
  )
  return response.data
}

/**
 * 获取画像Schema定义（用于表单生成）
 */
export async function getPortraitSchema(): Promise<any> {
  const response = await apiClient.get('/style/portraits/schema')
  return response.data
}
