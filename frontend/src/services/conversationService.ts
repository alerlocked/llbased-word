/**
 * 对话会话管理服务
 * 封装对话式生成相关的API调用
 */

import apiClient from './apiClient'

// 类型定义
export interface Question {
  id: string
  question: string
  question_type: string
  options: QuestionOption[]
  allow_custom: boolean
  required: boolean
}

export interface QuestionOption {
  id: string
  text: string
  description?: string
}

export interface PlanOption {
  id: string
  title: string
  angle: string
  structure: string[]
  focus: string
  estimated_words: number
  pros: string
  cons: string
  plan: any
}

export interface MaterialItem {
  id: string
  title: string
  content: string
  source: string
  material_type: string
  value_description: string
  priority: 'high' | 'medium' | 'low'
  relevance_score?: number
}

export interface MaterialReport {
  materials: MaterialItem[]
  recommendations: string[]
  priority_ranking: string[]
  summary?: string
}

export interface ReviewIssue {
  id: string
  type: 'content' | 'structure' | 'language' | 'logic'
  severity: 'high' | 'medium' | 'low'
  location: string
  description: string
  suggestions: ReviewSuggestion[]
}

export interface ReviewSuggestion {
  id: string
  description: string
  example?: string
  impact?: string
}

// 新增：Agent调用事件
export interface AgentCallEvent {
  type: 'agent_call'
  caller: string  // 调用者Agent名称
  target_agent: string  // 目标Agent名称
  capability: string  // 调用的能力
  reason: string  // 调用原因
  current_step: string
  message: string
}

// 新增：协作过程事件
export interface CollaborationEvent {
  type: 'collaboration'
  call_stack: string[]  // 调用栈
  command_results: Record<string, any>  // 命令执行结果
  current_step: string
  message: string
}

// 扩展SSE事件联合类型
export type SSEEvent = 
  | { type: 'progress'; node: string; current_step: string; message: string; data: any }
  | { type: 'plan_options'; session_id: string; plan_options: PlanOption[]; current_step: string; message: string }
  | { type: 'pending_questions'; session_id: string; questions: Question[]; current_step: string; message: string }
  | { type: 'result'; status: string; content: string; review?: any }
  | { type: 'error'; error: string }
  | AgentCallEvent
  | CollaborationEvent

/**
 * 启动对话式生成
 */
export async function startConversation(params: {
  initial_input: string
  reference_texts?: string[]
  business_scenario?: string
  project_id?: number
  user_id?: number
}): Promise<{
  session_id: string
  questions: Question[]
  current_state: string
}> {
  const response = await apiClient.post('/agent/start-conversation', params)
  return response.data
}

/**
 * 回复询问
 */
export async function replyQuestion(params: {
  session_id: string
  question_id: string
  answer: string
  selected_option_id?: string
}): Promise<{
  next_questions: Question[]
  plan_options: PlanOption[]
  status: 'asking' | 'planning' | 'ready'
}> {
  const response = await apiClient.post('/agent/reply-question', params)
  return response.data
}

/**
 * 选择/确认计划
 */
export async function selectPlan(params: {
  session_id: string
  plan_option_id: string
  custom_plan?: any
}): Promise<{
  selected_plan: any
  next_step: string
}> {
  const response = await apiClient.post('/agent/select-plan', params)
  return response.data
}

/**
 * 获取素材报告
 */
export async function getMaterialReport(sessionId: string): Promise<{
  report: MaterialReport
  status: string
}> {
  const response = await apiClient.get(`/agent/material-report/${sessionId}`)
  return response.data
}

/**
 * 确认素材
 */
export async function confirmMaterials(params: {
  session_id: string
  selected_material_ids: string[]
  excluded_material_ids?: string[]
  additional_keywords?: string[]
}): Promise<{
  confirmed: boolean
  next_step: string
}> {
  const response = await apiClient.post('/agent/confirm-materials', params)
  return response.data
}

/**
 * 获取评审建议
 */
export async function getReviewSuggestions(sessionId: string): Promise<{
  issues: ReviewIssue[]
  overall_score: number
  priority_ranking: string[]
}> {
  const response = await apiClient.get(`/agent/review-suggestions/${sessionId}`)
  return response.data
}

/**
 * 应用建议
 */
export async function applySuggestions(params: {
  session_id: string
  applied_suggestions: string[]
  rejected_suggestions?: string[]
  custom_changes?: Record<string, any>
}): Promise<{
  updated_content: string
  applied_count: number
  next_step: string
}> {
  const response = await apiClient.post('/agent/apply-suggestions', params)
  return response.data
}

