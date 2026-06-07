/**
 * Process document table layout — G12a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G12a: ProcessTableLayout = {
  chapterCode: 'G12a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '主要材料消耗工艺定额明细表', colspan: 6, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 3 },
    { label: '零、部、组(整)件名称', colspan: 3 },
    { label: '工艺文件编号', colspan: 6 },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 3 },
    { label: '', colspan: 6 },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '序号', rowspan: 2 },
      { label: '零件', colspan: 5 },
      { label: '材料名称、牌号、状态、品种、规格及标准号', colspan: 5, rowspan: 2 },
      { label: '坯料', colspan: 3 },
      { label: '计量单位' },
      { label: '每()产品工艺定额', colspan: 3 },
      { label: '材利用率%', rowspan: 2 },
      { label: '交往何处' },
    ],
    [
      { label: '代号' },
      { label: '名称', colspan: 2 },
      { label: '单套数量' },
      { label: '本批数量' },
      { label: '尺寸' },
      { label: '件数' },
      { label: '' },
      { label: '净重' },
      { label: '定额', colspan: 2 },
      { label: '' },
      { label: '' },
    ],
  ],
  dataColumns: [
    { key: '', label: '', colspan: 1 },
    { key: 'seq', label: '序号' },
    { key: 'part_code', label: '代号' },
    { key: 'part_name', label: '名称', colspan: 2 },
    { key: 'per_set_qty', label: '单套数量' },
    { key: 'batch_qty', label: '本批数量' },
    { key: 'material_desc', label: '材料名称', colspan: 5 },
    { key: 'blank_size', label: '坯料尺寸', colspan: 2 },
    { key: 'blank_count', label: '件数' },
    { key: 'blank_yield', label: '可制件数' },
    { key: 'unit', label: '计量单位' },
    { key: 'net_weight', label: '净重' },
    { key: 'quota', label: '定额', colspan: 2 },
    { key: 'utilization', label: '利用率%' },
    { key: 'destination', label: '交往何处' },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
}
