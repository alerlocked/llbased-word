/**
 * Process document table layout — G25a
 *
 * 装配工艺卡片 — 21 physical columns
 * Source: data/documents/1/content.html page 15
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G25a: ProcessTableLayout = {
  chapterCode: 'G25a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '装配工艺卡片', colspan: 6, rowspan: 2 },
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
  infoRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '单套产品中装配件数量', colspan: 3 },
      { label: '1', colspan: 2 },
      { label: '本批装配件生产总数', colspan: 3 },
      { label: '', colspan: 3 },
      { label: '交往何处', colspan: 3 },
      { label: '33', colspan: 5 },
    ],
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2, rowspan: 2 },
      { label: '车间', rowspan: 2 },
      { label: '工序号', rowspan: 2 },
      { label: '工序名称', rowspan: 2 },
      { label: '工序内容', colspan: 6, rowspan: 2 },
      { label: '辅助材料', colspan: 2, rowspan: 2 },
      { label: '专用仪器、仪表及工艺装备', colspan: 4, rowspan: 2 },
      { label: '工时定额h', colspan: 4 },
    ],
    [
      { label: '准结' },
      { label: '单件' },
      { label: '总计' },
      { label: '' },
    ],
  ],
  dataColumns: [
    { key: '', label: '', colspan: 2 },
    { key: 'workshop', label: '车间' },
    { key: 'step_no', label: '工序号' },
    { key: 'step_name', label: '工序名称' },
    { key: 'content', label: '工序内容', colspan: 6 },
    { key: 'aux_materials', label: '辅助材料', colspan: 2 },
    { key: 'instruments', label: '专用仪器、仪表及工艺装备', colspan: 4 },
    { key: 'time_setup', label: '准结' },
    { key: 'time_per_piece', label: '单件' },
    { key: 'time_total', label: '总计' },
    { key: '', label: '' },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
}
