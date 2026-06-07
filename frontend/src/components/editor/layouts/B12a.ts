/**
 * Process document table layout — B12a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const B12a: ProcessTableLayout = {
  chapterCode: 'B12a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '专用工具、量具明细表', colspan: 5, rowspan: 2 },
    { label: '产品数字', colspan: 3 },
    { label: '零、部、组(整)件代号', colspan: 3 },
    { label: '零、部、组(整)件名称', colspan: 2 },
    { label: '工艺文件编号', colspan: 5 },
    { label: '' },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 3 },
    { label: '', colspan: 2 },
    { label: '', colspan: 5 },
    { label: '' },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '序号', rowspan: 2 },
      { label: '专用工具', colspan: 5 },
      { label: '序号', rowspan: 2 },
      { label: '专用量具', colspan: 6 },
      { label: '备注', colspan: 5, rowspan: 2 },
      { label: '' },
    ],
    [
      { label: '名称' },
      { label: '型号或规格', colspan: 2 },
      { label: '数量', colspan: 2 },
      { label: '名称', colspan: 2 },
      { label: '型号或规格', colspan: 2 },
      { label: '数量', colspan: 2 },
      { label: '' },
    ],
  ],
  dataColumns: [
    { key: '', label: '', colspan: 3 },
    { key: 'tool_seq', label: '序号' },
    { key: 'tool_name', label: '名称' },
    { key: 'tool_spec', label: '型号或规格', colspan: 2 },
    { key: 'tool_qty', label: '数量', colspan: 2 },
    { key: 'gauge_seq', label: '序号' },
    { key: 'gauge_name', label: '名称', colspan: 2 },
    { key: 'gauge_spec', label: '型号或规格', colspan: 2 },
    { key: 'gauge_qty', label: '数量', colspan: 2 },
    { key: 'remarks', label: '备注', colspan: 5 },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4],
}
