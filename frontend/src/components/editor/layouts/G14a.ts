/**
 * Process document table layout — G14a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G14a: ProcessTableLayout = {
  chapterCode: 'G14a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '辅助材料消耗工艺定额明细表', colspan: 5, rowspan: 2 },
    { label: '产品数字', colspan: 3 },
    { label: '零、部、组(整)件代号', colspan: 3 },
    { label: '零、部、组(整)件名称', colspan: 3 },
    { label: '工艺文件编号', colspan: 5 },
    { label: '' },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 3 },
    { label: '', colspan: 3 },
    { label: '', colspan: 5 },
    { label: '' },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2, rowspan: 7 },
      { label: '序号', rowspan: 2 },
      { label: '零、部、组(整)件', colspan: 6 },
      { label: '材 料', colspan: 5 },
      { label: '计量单位', rowspan: 2 },
      { label: '工艺定额', colspan: 3 },
      { label: '备注', colspan: 2, rowspan: 2 },
      { label: '' },
      { label: '' },
    ],
    [
      { label: '代 号', colspan: 2 },
      { label: '名 称', colspan: 2 },
      { label: '单套数量' },
      { label: '本批数量' },
      { label: '名称、牌号、状态、品种规格及标准号', colspan: 5 },
      { label: '单套' },
      { label: '本批', colspan: 2 },
      { label: '' },
      { label: '' },
    ],
  ],
  dataColumns: [
    { key: 'seq', label: '序号' },
    { key: 'comp_code', label: '代号', colspan: 2 },
    { key: 'comp_name', label: '名称', colspan: 2 },
    { key: 'per_set_qty', label: '单套数量' },
    { key: 'batch_qty', label: '本批数量' },
    { key: 'material_desc', label: '材料名称', colspan: 5 },
    { key: 'unit', label: '计量单位' },
    { key: 'per_set_quota', label: '单套定额' },
    { key: 'batch_quota', label: '本批定额', colspan: 2 },
    { key: 'remarks', label: '备注', colspan: 2 },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
}
