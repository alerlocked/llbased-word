/**
 * Process document table layout — G22a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G22a: ProcessTableLayout = {
  chapterCode: 'G22a',
  titleRow0: [
    { label: '配套明细表(续)', colspan: 6, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 2 },
    { label: '零、部、组(整)件名称', colspan: 2 },
    { label: '工艺文件编号', colspan: 2 },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
  ],
  headerRows: [
    [
      { label: '号序', rowspan: 2 },
      { label: '装配件中零、部、组(整)件', colspan: 5 },
      { label: '数量', colspan: 3 },
      { label: '来自何处', rowspan: 2 },
      { label: '备注', colspan: 4, rowspan: 2 },
    ],
    [
      { label: '代号', colspan: 2 },
      { label: '名称', colspan: 3 },
      { label: '每装配件' },
      { label: '总计', colspan: 2 },
    ],
  ],
  dataColumns: [
    { key: 'seq', label: '序号' },
    { key: 'part_code', label: '装配件代号', colspan: 2 },
    { key: 'part_name', label: '装配件名称', colspan: 3 },
    { key: 'qty_per', label: '每装配件数量' },
    { key: 'qty_total', label: '总计', colspan: 2 },
    { key: 'source', label: '来自何处' },
    { key: 'remarks', label: '备注', colspan: 4 },
  ],
  colWidths: [8, 8, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7],
}
