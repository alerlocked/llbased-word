/**
 * Process document table layout definitions.
 *
 * Precisely mirrors the actual parsed document (data/documents/1/content.html).
 * Each chapter layout is in a separate file under ./layouts/
 */

export interface HeaderCell {
  label: string
  colspan?: number
  rowspan?: number
}

export interface DataColumn {
  /** Matches filled_data object key */
  key: string
  label: string
  width?: string
  /** How many physical columns this data field spans in the source document */
  colspan?: number
}

export interface ProcessTableLayout {
  chapterCode: string
  titleRow0: HeaderCell[]
  titleRow1: HeaderCell[]
  infoRows?: HeaderCell[][]
  headerRows: HeaderCell[][]
  dataColumns: DataColumn[]
  /**
   * Width (%) of every physical column in left-to-right order.
   * Used to render <colgroup> so colspan cells align perfectly.
   */
  colWidths: number[]
}

import { G4a } from './layouts/G4a'
import { G5a } from './layouts/G5a'
import { G10a } from './layouts/G10a'
import { B12a } from './layouts/B12a'
import { G12a } from './layouts/G12a'
import { G14a } from './layouts/G14a'
import { G18a } from './layouts/G18a'
import { G22a } from './layouts/G22a'
import { G25a } from './layouts/G25a'

export const LAYOUTS: Record<string, ProcessTableLayout> = {
  G4a,
  G5a,
  G10a,
  B12a,
  G12a,
  G14a,
  G18a,
  G22a,
  G25a,
  G18b: G18a,
  G22b: G22a,
  G25b: G25a,
}

export function getLayout(chapterCode: string): ProcessTableLayout | undefined {
  const raw = LAYOUTS[chapterCode]
  return raw ? stripCountersign(raw) : undefined
}

/**
 * Strip the countersign (会签) column and rebalance column widths.
 *
 * The auto-generated layouts prepend a "会签" column whose colspan is
 * inconsistent across chapters (1–4) and which overlaps the title row's
 * 产品工号 cell, causing the header and data grids to misalign. Users don't
 * fill 会签 in the editor (it's a PDF-export artifact), so we drop it.
 *
 * Strategy: remove the first data column (empty key) and the first cell of
 * every row (title / info / header / data), then rebuild colWidths so every
 * row's colspan sum matches the new physical column count. Each remaining
 * column gets an equal share of 100%.
 */
function stripCountersign(layout: ProcessTableLayout): ProcessTableLayout {
  const firstData = layout.dataColumns[0]
  // Only strip when the leading column is the empty countersign placeholder
  if (!firstData || firstData.key !== '' || firstData.label !== '') {
    return layout
  }

  const dropDataCols = firstData.colspan || 1
  const remainingData = layout.dataColumns.slice(1)
  // New physical column count = sum of remaining data colspans (>= count)
  const newWidth = remainingData.reduce((s, c) => s + (c.colspan || 1), 0)
  const equalW = +(100 / newWidth).toFixed(2)
  const newColWidths = Array.from({ length: newWidth }, () => equalW)

  /** Drop the first cell of a row, then pad/trim so colspans sum to target.
   *  Trailing empty-label cells are removed first (auto-gen noise). */
  const rebalance = (row: HeaderCell[], target: number): HeaderCell[] => {
    if (row.length === 0) return row
    let rest = row.slice(1)
    // Drop trailing empty cells while over target
    while (
      rest.length > 1 &&
      rest.reduce((s, c) => s + (c.colspan || 1), 0) > target &&
      rest[rest.length - 1].label === ''
    ) {
      rest = rest.slice(0, -1)
    }
    const sum = rest.reduce((s, c) => s + (c.colspan || 1), 0)
    if (sum === target || rest.length === 0) return rest
    // Adjust the last cell's colspan to hit the target
    const last = { ...rest[rest.length - 1] }
    last.colspan = Math.max(1, (last.colspan || 1) + (target - sum))
    return [...rest.slice(0, -1), last]
  }

  const titleRow0 = rebalance(layout.titleRow0, newWidth)
  const titleRow1 = rebalance(layout.titleRow1, newWidth)
  const infoRows = layout.infoRows?.map((r) => rebalance(r, newWidth))
  // Only headerRows[0] holds the 会签 cell (rowspan:2). Sub-rows sit under
  // grouped headers and reflow automatically once the rowspan cell is gone,
  // so we must NOT drop their first cell.
  const headerRows = layout.headerRows.map((r, i) =>
    i === 0 ? rebalance(r, newWidth) : r,
  )

  return {
    ...layout,
    titleRow0,
    titleRow1,
    infoRows,
    headerRows,
    dataColumns: remainingData.map((c) => ({ ...c })),
    colWidths: newColWidths,
  }
}
