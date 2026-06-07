/**
 * Process document table layout — G4a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G4a: ProcessTableLayout = {
  chapterCode: 'G4a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '工艺文件目录', colspan: 5, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 3 },
    { label: '零、部、组(整)件名称', colspan: 3 },
    { label: '工艺文件编号', colspan: 5 },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 3 },
    { label: '', colspan: 5 },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2, rowspan: 7 },
      { label: '序号', rowspan: 2 },
      { label: '工艺文件', colspan: 6 },
      { label: '零、部、组(整)件', colspan: 5 },
      { label: '页数', colspan: 2, rowspan: 2 },
      { label: '册数', rowspan: 2 },
      { label: '备注', colspan: 3, rowspan: 2 },
    ],
    [
      { label: '名称', colspan: 2 },
      { label: '编号', colspan: 4 },
      { label: '代号', colspan: 2 },
      { label: '名称', colspan: 3 },
    ],
  ],
  dataColumns: [
    { key: 'seq', label: '序号' },
    { key: 'doc_name', label: '文件名称', colspan: 2 },
    { key: 'doc_number', label: '文件编号', colspan: 4 },
    { key: 'component_code', label: '零部组件代号', colspan: 2 },
    { key: 'component_name', label: '零部组件名称', colspan: 3 },
    { key: 'pages', label: '页数', colspan: 2 },
    { key: 'volume', label: '册数' },
    { key: 'remarks', label: '备注', colspan: 3 },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
}
