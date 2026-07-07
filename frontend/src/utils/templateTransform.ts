import type { StructuredDocument, TemplateSection } from '../types/template'

function mapTableType(tableType: string): TemplateSection['content_type'] {
  const mapping: Record<string, TemplateSection['content_type']> = {
    single_row_list: 'table',
    process_card: 'table',
    assembly_card: 'table',
    dual_list: 'dual_table',
    flow_chart: 'flow_chart',
    fields: 'fields',
  }
  return mapping[tableType] || 'text'
}

/**
 * Convert a backend StructuredDocument (template_data) to the editor's
 * TemplateSection[] shape. Shared by WorkspacePage (rendering) and
 * AIChatPanel (snapshot capture for feedback diff). feedback-rules 节点4a.
 */
export function structuredDocToSections(doc: StructuredDocument): TemplateSection[] {
  return doc.chapters.map((ch) => {
    const allKeys = [
      ...(ch.fill_sources?.structured || []),
      ...(ch.fill_sources?.unstructured || []),
    ]
    return {
      section_id: ch.chapter_code,
      title: ch.chapter_title,
      content_type: mapTableType(ch.table_type),
      columns: allKeys,
      column_keys: allKeys,
      rows: ch.filled_data || [],
      left_data: ch.left_data,
      right_data: ch.right_data,
      flow_steps: ch.flow_steps,
      field_values: ch.field_values,
      fill_sources: ch.fill_sources,
      review_passed: true,
      source: 'template_generated',
      table_type: ch.table_type,
    }
  })
}
