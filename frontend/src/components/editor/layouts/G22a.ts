/**
 * Process document table layout — G22a
 *
 * 工艺过程卡 — 21 physical columns
 * Source: data/documents/1/content.html page 13
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G22a: ProcessTableLayout = {
  chapterCode: 'G22a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '工艺过程卡', colspan: 6, rowspan: 2 },
    { label: '产品数字', colspan: 3 },
    { label: '零、部、组(整)件代号', colspan: 2 },
    { label: '零、部、组(整)件名称', colspan: 3 },
    { label: '工艺文件编号', colspan: 5 },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 2 },
    { label: '', colspan: 3 },
    { label: '', colspan: 5 },
  ],
  infoRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '材料', colspan: 4 },
      { label: '零件数量', colspan: 3 },
      { label: '坯料尺寸', colspan: 4 },
      { label: '坯料可制件数', colspan: 2 },
      { label: '坯料件数', colspan: 6 },
    ],
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2, rowspan: 2 },
      { label: '车间', rowspan: 2 },
      { label: '工序号', rowspan: 2 },
      { label: '工序名称', rowspan: 2 },
      { label: '工序内容简述', colspan: 6, rowspan: 2 },
      { label: '设备', colspan: 2, rowspan: 2 },
      { label: '工艺装备及专用刀、量具', colspan: 3, rowspan: 2 },
      { label: '工时定额h', colspan: 5 },
    ],
    [
      { label: '准结', colspan: 2 },
      { label: '单件' },
      { label: '总计', colspan: 2 },
    ],
  ],
  dataColumns: [
    { key: '', label: '', colspan: 2 },
    { key: 'workshop', label: '车间' },
    { key: 'step_no', label: '工序号' },
    { key: 'step_name', label: '工序名称' },
    { key: 'step_desc', label: '工序内容简述', colspan: 6 },
    { key: 'equipment', label: '设备', colspan: 2 },
    { key: 'tooling', label: '工艺装备及专用刀、量具', colspan: 3 },
    { key: 'time_setup', label: '准结', colspan: 2 },
    { key: 'time_per_piece', label: '单件' },
    { key: 'time_total', label: '总计', colspan: 2 },
  ],
  colWidths: [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
}
