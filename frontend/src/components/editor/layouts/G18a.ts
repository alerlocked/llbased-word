/**
 * Process document table layout — G18a
 *
 * Auto-generated from data/documents/1/content.html
 */
import type { ProcessTableLayout } from '../processDocumentLayouts'

export const G18a: ProcessTableLayout = {
  chapterCode: 'G18a',
  titleRow0: [
    { label: '产品工号', colspan: 2 },
    { label: '工艺流程图', colspan: 4, rowspan: 2 },
    { label: '产品数字', colspan: 2 },
    { label: '零、部、组(整)件代号', colspan: 2 },
    { label: '零、部、组(整)件名称', colspan: 2 },
    { label: '工艺文件编号', colspan: 6 },
  ],
  titleRow1: [
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 2 },
    { label: '', colspan: 6 },
  ],
  headerRows: [
    [
      { label: '会签', colspan: 2 },
      { label: '装前准备', colspan: 2 },
      { label: '安装密封圈2', colspan: 2 },
      { label: '安装行程延时开关组合', colspan: 2 },
      { label: '四五舱对接', colspan: 2 },
      { label: '五舱装配', colspan: 8 },
    ],
  ],
  dataColumns: [
    { key: 'step_check', label: '检查累计', colspan: 2 },
    { key: 'step_prep', label: '装配前准备', colspan: 2 },
    { key: 'step_assembly', label: '装配操作', colspan: 2 },
    { key: 'step_equipment', label: '使用设备及工装', colspan: 2 },
    { key: 'step_inspection', label: '工艺纪律检查及工装', colspan: 8 },
  ],
  colWidths: [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5],
}
