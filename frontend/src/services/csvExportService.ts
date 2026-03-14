import apiClient from './apiClient';

interface ExportCSVOptions {
  tableIds?: string[];
  includeMetadata?: boolean;
  mergeMultipage?: boolean;
}

interface ExportCSVResult {
  export_id: string;
  doc_id: string;
  total_tables: number;
  total_rows: number;
  files: Array<{
    table_id: string;
    filename: string;
    rows: number;
    columns: number;
  }>;
  download_url: string;
  manifest_file: string;
}

class CSVExportService {
  async exportToCSV(docId: string, options: ExportCSVOptions): Promise<ExportCSVResult> {
    try {
      const response = await apiClient.post(`/process-documents/${docId}/export-csv`, {
        table_ids: options.tableIds,
        include_metadata: options.includeMetadata ?? true,
        merge_multipage: options.mergeMultipage ?? true
      });

      return response.data;
    } catch (error) {
      console.error('Failed to export CSV:', error);
      throw error;
    }
  }

  async downloadCSV(docId: string, exportId: string, filename?: string): Promise<Blob> {
    try {
      const url = `/process-documents/${docId}/csv/${exportId}`;
      const params = filename ? { params: { filename } } : {};

      const response = await apiClient.get(url, {
        ...params,
        responseType: 'blob'
      });

      return response.data;
    } catch (error) {
      console.error('Failed to download CSV:', error);
      throw error;
    }
  }

  async getParserConfig(docId: string): Promise<any> {
    try {
      const response = await apiClient.get(`/process-documents/${docId}/parser-config`);
      return response.data;
    } catch (error) {
      console.error('Failed to get parser config:', error);
      throw error;
    }
  }

  async getCSVConfig(): Promise<any> {
    try {
      const response = await apiClient.get('/process-documents/csv-config');
      return response.data;
    } catch (error) {
      console.error('Failed to get CSV config:', error);
      throw error;
    }
  }
}

export const csvExportService = new CSVExportService();