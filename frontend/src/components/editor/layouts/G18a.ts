/**
 * Process document table layout — G18a
 *
 * 配套明细表 (Matching Parts List) — 22 physical columns
 * Columns: 序号, 代号, 名称, 每装配件数量, 总计数量, 来自何处, 备注
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G18a: ProcessTableLayout = {
  chapterCode: 'G18a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '配套明细表', colspan: 6, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 3 },
    { label: '零、部、组(整)件名称', colspan: 3 },
    { label: '工艺文件编号', colspan: 5 },
    { label: '' },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 3 },
    { label: '', colspan: 5 },
    { label: '' },
  ],
  infoRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '单套产品中装配件数量', colspan: 4 },
      { label: '', colspan: 2 },
      { label: '本批装配件生产总数', colspan: 4 },
      { label: '', colspan: 4 },
      { label: '交往何处', colspan: 3 },
      { label: '', colspan: 3 },
    ],
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2, rowspan: 2 },
      { label: '序号', rowspan: 2 },
      { label: '代 号', colspan: 3, rowspan: 2 },
      { label: '名 称', colspan: 4, rowspan: 2 },
      { label: '数 量', colspan: 4 },
      { label: '来自何处', colspan: 3, rowspan: 2 },
      { label: '备注', colspan: 5, rowspan: 2 },
    ],
    [
      { label: '每装配件', colspan: 2 },
      { label: '总 计', colspan: 2 },
    ],
  ],
  dataColumns: [
    { key: '', label: '', colspan: 2 },
    { key: 'seq', label: '序号' },
    { key: 'part_code', label: '代号', colspan: 3 },
    { key: 'part_name', label: '名称', colspan: 4 },
    { key: 'qty_per_assembly', label: '每装配件数量', colspan: 2 },
    { key: 'qty_total', label: '总计数量', colspan: 2 },
    { key: 'source', label: '来自何处', colspan: 3 },
    { key: 'remarks', label: '备注', colspan: 5 },
  ],
  colWidths: [4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 5, 5, 5, 5, 5, 5, 5, 4, 4],
}
