/**
 * Template type definitions for structured document generation.
 *
 * Mirrors backend template_types.py for frontend rendering.
 */

export interface TemplateColumn {
  key: string
  label: string
  type: 'text' | 'number' | 'long_text' | 'select' | 'ordered_list'
  required: boolean
  ai_filled: boolean
  fill_type?: 'structured' | 'unstructured'
  default?: string
  options?: string[]
}

export interface TemplateChapter {
  code: string
  title: string
  table_type: 'single_row_list' | 'process_card' | 'dual_list' | 'flow_chart' | 'fields'
  columns: TemplateColumn[]
  editor_visible: boolean
  pages: number | 'variable'
  ai_guidance: string
  header_extra: Array<Record<string, unknown>>
  sub_sections: Array<Record<string, unknown>>
  left_section?: {
    title: string
    columns: TemplateColumn[]
  }
  right_section?: {
    title: string
    columns: TemplateColumn[]
  }
  fields: Array<Record<string, unknown>>
  continuation_code?: string
  continuation_title?: string
}

export interface ChapterData {
  chapter_code: string
  chapter_title: string
  table_type: string
  filled_data: Array<Record<string, unknown>>
  left_data?: Array<Record<string, unknown>>
  right_data?: Array<Record<string, unknown>>
  flow_steps?: string[]
  field_values?: Record<string, unknown>
  fill_sources?: {
    structured: string[]
    unstructured: string[]
  }
}

export interface StructuredDocument {
  template_id: string
  template_name: string
  chapters: ChapterData[]
  footer_values: Record<string, unknown>
}

/** Content.json v3 section as received from backend */
export interface TemplateSection {
  section_id: string
  title: string
  content_type: 'table' | 'dual_table' | 'flow_chart' | 'fields' | 'text'
  table_type?: string
  columns: string[]
  column_keys?: string[]
  rows: Array<Record<string, unknown>>
  left_data?: Array<Record<string, unknown>>
  right_data?: Array<Record<string, unknown>>
  left_columns?: string[]
  right_columns?: string[]
  flow_steps?: string[]
  field_values?: Record<string, unknown>
  fill_sources?: {
    structured: string[]
    unstructured: string[]
  }
  review_passed: boolean
  source: string
}

/** Full content.json v3 response from backend */
export interface TemplateContentResponse {
  version: 3
  template_id: string
  template_name: string
  content_format: 'template'
  sections: TemplateSection[]
}
