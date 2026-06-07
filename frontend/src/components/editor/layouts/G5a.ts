/**
 * Process document table layout — G5a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G5a: ProcessTableLayout = {
  chapterCode: 'G5a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '引(借)用文件目录', colspan: 5, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 3 },
    { label: '零、部、组(整)件名称', colspan: 4 },
    { label: '工艺文件编号', colspan: 5 },
    { label: '' },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 4 },
    { label: '', colspan: 5 },
    { label: '' },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2, rowspan: 7 },
      { label: '序号' },
      { label: '代号', colspan: 3 },
      { label: '文件名称', colspan: 7 },
      { label: '页数' },
      { label: '备注', colspan: 7 },
      { label: '' },
    ],
  ],
  dataColumns: [
    { key: 'seq', label: '序号' },
    { key: 'ref_code', label: '代号', colspan: 3 },
    { key: 'ref_name', label: '文件名称', colspan: 7 },
    { key: 'pages', label: '页数' },
    { key: 'remarks', label: '备注', colspan: 7 },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
}
