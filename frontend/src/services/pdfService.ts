/**
 * PDF相关API服务
 * 基于现有apiClient模式，提供PDF文档处理相关API调用
 */
import apiClient from './apiClient';

// 基于后端API实际响应定义类型
export interface PDFDocument {
  id: string;
  name: string;
  path: string;
  size: number;
  created_at: number;
  has_extracted: boolean;
  extracted_path?: string;
}

export interface PDFTableRow {
  cells: string[];
  bbox: number[];
  text: string;
}

export interface PDFTable {
  table_id: string;
  page_number: number;
  method: string;
  rows: PDFTableRow[];
  row_count: number;
  col_count: number;
  table_type: string;
}

export interface PDFExtractionResult {
  tables: PDFTable[];
  process_parameters: {
    spindle_speeds: string[];
    cutting_speeds: string[];
    feed_rates: string[];
    cutting_depths: string[];
    surface_roughness: string[];
    dimensional_accuracy: string[];
  };
  metadata: {
    pdf_path: string;
    table_count: number;
    process_card_count: number;
    parameter_table_count: number;
    extraction_timestamp: string;
  };
}

export interface PDFDocumentView {
  doc_id: string;
  metadata: any;
  summary: {
    total_tables: number;
    by_type: {
      process_cards: number;
      operation_cards: number;
      tool_lists: number;
      parameter_tables: number;
    };
  };
  content: {
    process_cards: any[];
    operation_cards: any[];
    tool_lists: any[];
    parameter_tables: any[];
    process_flow: any[];
    quality_requirements: any[];
  };
  process_steps: string[];
}

export interface PDFToolItem {
  name: string;
  specification: string;
  page: number;
  row_index: number;
}

class PDFService {
  // 列出所有PDF文档
  async listDocuments(): Promise<{ documents: PDFDocument[]; count: number }> {
    const response = await apiClient.get('/process-documents/');
    return response.data;
  }

  // 获取文档查看数据
  async getDocumentView(docId: string): Promise<PDFDocumentView> {
    const response = await apiClient.get(`/process-documents/${docId}/view`);
    return response.data;
  }

  // 获取文档摘要
  async getDocumentSummary(docId: string): Promise<any> {
    const response = await apiClient.get(`/process-documents/${docId}/summary`);
    return response.data;
  }

  // 获取特定类型表格
  async getTablesByType(docId: string, tableType: string): Promise<any> {
    const response = await apiClient.get(`/process-documents/${docId}/tables/${tableType}`);
    return response.data;
  }

  // 获取工具清单
  async getToolList(docId: string): Promise<{ doc_id: string; tools: PDFToolItem[]; total: number }> {
    const response = await apiClient.get(`/process-documents/${docId}/tools`);
    return response.data;
  }

  // 重新提取文档
  async reExtractDocument(docId: string): Promise<PDFExtractionResult> {
    const response = await apiClient.post(`/process-documents/${docId}/extract`);
    return response.data;
  }

  // 删除提取内容
  async deleteExtractedContent(docId: string): Promise<any> {
    const response = await apiClient.delete(`/process-documents/${docId}/extracted`);
    return response.data;
  }
}

export const pdfService = new PDFService();