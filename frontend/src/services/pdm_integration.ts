import axios from 'axios';
import { ProcessDocument } from '../types/process';

interface PDMExportOptions {
  format: 'json' | 'pdf' | 'word';
  overwrite?: boolean;
  notifyUsers?: string[];
}

interface PDMExportResult {
  success: boolean;
  exportId: string;
  documentId: string;
  pdmSystem: string;
  exportedFiles: string[];
  exportTime: string;
  status: 'completed' | 'failed' | 'pending';
  error?: string;
}

interface PDMImportResult {
  success: boolean;
  documentId: string;
  importedData: ProcessDocument;
  importTime: string;
  status: 'completed' | 'failed' | 'pending';
  error?: string;
}

const PDM_API_BASE = '/api/pdm-integration';

export class PDMIntegrationService {
  /**
   * 导出工艺文件到PDM系统
   * @param document 工艺文件
   * @param options 导出选项
   * @returns 导出结果
   */
  static async exportToPDM(
    document: ProcessDocument,
    options: PDMExportOptions
  ): Promise<PDMExportResult> {
    try {
      const response = await axios.post(`${PDM_API_BASE}/export`, {
        document,
        options
      });

      return response.data;
    } catch (error) {
      console.error('Failed to export to PDM:', error);
      throw new Error(`导出失败: ${(error as Error).message}`);
    }
  }

  /**
   * 从PDM系统导入工艺文件
   * @param documentId 工艺文件ID
   * @returns 导入结果
   */
  static async importFromPDM(documentId: string): Promise<PDMImportResult> {
    try {
      const response = await axios.get(`${PDM_API_BASE}/import/${documentId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to import from PDM:', error);
      throw new Error(`导入失败: ${(error as Error).message}`);
    }
  }

  /**
   * 获取PDM系统状态
   * @returns PDM系统状态
   */
  static async getPDMStatus(): Promise<{
    connected: boolean;
    systemName: string;
    version: string;
    lastSyncTime?: string;
  }> {
    try {
      const response = await axios.get(`${PDM_API_BASE}/status`);
      return response.data;
    } catch (error) {
      console.error('Failed to get PDM status:', error);
      return {
        connected: false,
        systemName: 'Unknown',
        version: 'Unknown'
      };
    }
  }

  /**
   * 同步工艺文件到PDM
   * @param documentId 工艺文件ID
   * @returns 同步结果
   */
  static async syncToPDM(documentId: string): Promise<{
    success: boolean;
    syncId: string;
    documentId: string;
    syncTime: string;
    changes: number;
  }> {
    try {
      const response = await axios.post(`${PDM_API_BASE}/sync/${documentId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to sync to PDM:', error);
      throw new Error(`同步失败: ${(error as Error).message}`);
    }
  }

  /**
   * 获取PDM中的工艺文件列表
   * @returns 工艺文件列表
   */
  static async getPDMDocuments(): Promise<Array<{
    id: string;
    name: string;
    lastModified: string;
    status: string;
  }>> {
    try {
      const response = await axios.get(`${PDM_API_BASE}/documents`);
      return response.data.documents;
    } catch (error) {
      console.error('Failed to get PDM documents:', error);
      return [];
    }
  }
}

export default PDMIntegrationService;