/**
 * Draft API 服务
 * 封装初稿上传、版本历史、回滚、差异比较、导出等 API 调用
 */
import apiClient from './apiClient'

// ========== 类型定义 ==========

export interface DraftVersion {
  id: number
  draft_id: number
  snapshot_content: string
  snapshot_source: 'upload' | 'user_edit' | 'ai_completion' | 'rollback'
  created_at: string
}

export interface Draft {
  id: number
  project_id: number
  title: string
  content: string
  source: string
  current_version_id: number
  created_at: string
  updated_at: string
}

export interface DraftDiff {
  v1_id: number
  v2_id: number
  diff_html: string
  summary: string
}

export interface UploadDraftResponse {
  id: number
  title: string
  content: string
  version_id: number
  message: string
}

// ========== API 服务 ==========

class DraftApiService {
  /**
   * 上传初稿文件（PDF）
   */
  async uploadDraft(file: File, projectId?: number): Promise<UploadDraftResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (projectId !== undefined) {
      formData.append('project_id', String(projectId))
    }
    const response = await apiClient.post('/drafts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  }

  /**
   * 获取初稿列表
   */
  async listDrafts(projectId?: number): Promise<{ drafts: Draft[]; total: number }> {
    const params: Record<string, string> = {}
    if (projectId !== undefined) {
      params.project_id = String(projectId)
    }
    const response = await apiClient.get('/drafts', { params })
    return response.data
  }

  /**
   * 获取单个初稿详情
   */
  async getDraft(id: number): Promise<Draft> {
    const response = await apiClient.get(`/drafts/${id}`)
    return response.data
  }

  /**
   * 获取初稿的版本列表
   */
  async listVersions(draftId: number): Promise<{ versions: DraftVersion[]; total: number }> {
    const response = await apiClient.get(`/drafts/${draftId}/versions`)
    return response.data
  }

  /**
   * 获取特定版本详情
   */
  async getVersion(draftId: number, versionId: number): Promise<DraftVersion> {
    const response = await apiClient.get(`/drafts/${draftId}/versions/${versionId}`)
    return response.data
  }

  /**
   * 回滚到指定版本
   */
  async rollback(draftId: number, versionId: number): Promise<{ draft: Draft; new_version_id: number; message: string }> {
    const response = await apiClient.post(`/drafts/${draftId}/rollback/${versionId}`)
    return response.data
  }

  /**
   * 比较两个版本的差异
   */
  async getDiff(draftId: number, v1: number, v2: number): Promise<DraftDiff> {
    const response = await apiClient.get(`/drafts/${draftId}/diff`, {
      params: { v1, v2 },
    })
    return response.data
  }

  /**
   * 导出为 PDF 文件（触发下载）
   */
  async exportPdf(draftId: number): Promise<void> {
    const response = await apiClient.post(`/drafts/${draftId}/export/pdf`, null, {
      responseType: 'blob',
    })
    downloadBlob(response.data, `draft_${draftId}.pdf`)
  }

  /**
   * 导出为 Word 文件（触发下载）
   */
  async exportWord(draftId: number): Promise<void> {
    const response = await apiClient.post(`/drafts/${draftId}/export/word`, null, {
      responseType: 'blob',
    })
    downloadBlob(response.data, `draft_${draftId}.docx`)
  }
}

// ========== 工具函数 ==========

/**
 * 触发浏览器文件下载
 */
function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}

export const draftApi = new DraftApiService()
