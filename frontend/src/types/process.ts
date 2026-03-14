/**
 * 工艺文档类型定义
 */

export interface ProcessOperation {
  id: string;
  sequence: number;
  name: string;
  description: string;
  tools: string[];
  parameters: Record<string, any>;
}

export interface QualityRequirement {
  id: string;
  description: string;
  standard: string;
  tolerance: string;
}

export interface ProcessDocument {
  id: string;
  name: string;
  operations: ProcessOperation[];
  parameters: Record<string, any>;
  qualityRequirements: QualityRequirement[];
}

export interface ProcessDocumentSummary {
  docId: string;
  totalTables: number;
  byType: {
    processCards: number;
    operationCards: number;
    toolLists: number;
    parameterTables: number;
  };
  processStepsCount: number;
  pageCount: number;
  extractionTimestamp: string;
}
