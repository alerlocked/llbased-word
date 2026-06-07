/**
 * Process document table layout — G10a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G10a: ProcessTableLayout = {
  chapterCode: 'G10a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '专用工艺装备明细表', colspan: 5, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 2 },
    { label: '零、部、组(整)件名称', colspan: 2 },
    { label: '工艺文件编号', colspan: 5 },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 5 },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '序号', rowspan: 2 },
      { label: '专用工艺装备', colspan: 5 },
      { label: '用于零、部、组(整)件', colspan: 4 },
      { label: '使用单位', rowspan: 2 },
      { label: '备注', colspan: 5, rowspan: 2 },
    ],
    [
      { label: '编号' },
      { label: '名称', colspan: 2 },
      { label: '类别' },
      { label: '数量' },
      { label: '代号', colspan: 2 },
      { label: '名称', colspan: 2 },
    ],
  ],
  dataColumns: [
    { key: '', label: '', colspan: 2 },
    { key: 'seq', label: '序号' },
    { key: 'equipment_code', label: '编号' },
    { key: 'equipment_name', label: '名称', colspan: 2 },
    { key: 'category', label: '类别' },
    { key: 'quantity', label: '数量' },
    { key: 'for_code', label: '代号', colspan: 2 },
    { key: 'for_name', label: '名称', colspan: 2 },
    { key: 'usage_unit', label: '使用单位' },
    { key: 'remarks', label: '备注', colspan: 5 },
  ],
  colWidths: [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5],
}
