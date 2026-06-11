/**
 * mergeUtils — pure helpers for vertical cell merging in template tables.
 *
 * Merge state is stored per-column as ascending, non-overlapping ranges.
 * All functions are pure (no React, no DOM) and return new objects.
 */
import type { CellMerge, TemplateSection } from '../../types/template'

/** Render-time classification of a single cell. */
export type CellState =
  | { kind: 'normal' }
  | { kind: 'merge-start'; rowSpan: number }
  | { kind: 'merged-out' }

/**
 * Classify the cell at (rowIndex, colKey) given the merge map.
 * - normal: standalone editable cell
 * - merge-start: top of a merge, render <td rowSpan={span}>
 * - merged-out: swallowed by a merge above, render nothing
 */
export function cellStateFor(
  merges: Record<string, CellMerge[]> | undefined,
  colKey: string,
  rowIndex: number,
): CellState {
  const list = merges?.[colKey]
  if (!list || list.length === 0) return { kind: 'normal' }
  const m = list.find(
    (r) => rowIndex >= r.startRow && rowIndex < r.startRow + r.span,
  )
  if (!m) return { kind: 'normal' }
  if (rowIndex === m.startRow) return { kind: 'merge-start', rowSpan: m.span }
  return { kind: 'merged-out' }
}

/** Find the merge range covering (colKey, rowIndex), if any. */
export function findMergeAt(
  merges: Record<string, CellMerge[]> | undefined,
  colKey: string,
  rowIndex: number,
): CellMerge | undefined {
  const list = merges?.[colKey]
  if (!list) return undefined
  return list.find(
    (r) => rowIndex >= r.startRow && rowIndex < r.startRow + r.span,
  )
}

/**
 * Shift merge ranges when rows are inserted (+1) at `atRow`.
 * Ranges entirely at/after atRow move down by delta.
 * Ranges spanning atRow extend by delta (the new row joins the merge).
 */
export function shiftMerges(
  merges: Record<string, CellMerge[]> | undefined,
  atRow: number,
  delta: number,
): Record<string, CellMerge[]> | undefined {
  if (!merges) return undefined
  const next: Record<string, CellMerge[]> = {}
  for (const [colKey, list] of Object.entries(merges)) {
    next[colKey] = list
      .map((r) => {
        // Range entirely at or after the insertion point → shift down
        if (r.startRow >= atRow) {
          return { ...r, startRow: r.startRow + delta }
        }
        // Range spanning the insertion point (start < atRow < start+span) → grow
        if (r.startRow < atRow && r.startRow + r.span > atRow) {
          return { ...r, span: r.span + delta }
        }
        // Range entirely before the insertion point → untouched
        return r
      })
      .filter((r) => r.span >= 2) // collapse degenerate ranges
  }
  return next
}

/**
 * Remove a row from the merge map (used on row deletion).
 * If the deleted row sits inside a merge, that merge's span shrinks by 1;
 * a merge that drops to span 1 is removed entirely.
 */
export function removeRowFromMerges(
  merges: Record<string, CellMerge[]> | undefined,
  rowIndex: number,
): Record<string, CellMerge[]> | undefined {
  if (!merges) return undefined
  const next: Record<string, CellMerge[]> = {}
  let anyKept = false
  for (const [colKey, list] of Object.entries(merges)) {
    const adjusted: CellMerge[] = []
    for (const r of list) {
      const end = r.startRow + r.span // exclusive
      if (rowIndex < r.startRow || rowIndex >= end) {
        // Outside the deleted row: shift if it comes after
        const startRow = rowIndex < r.startRow ? r.startRow - 1 : r.startRow
        adjusted.push({ ...r, startRow })
      } else {
        // Deleted row is inside this merge: shrink span
        const span = r.span - 1
        if (span >= 2) adjusted.push({ ...r, span })
      }
    }
    if (adjusted.length > 0) {
      next[colKey] = adjusted
      anyKept = true
    }
  }
  return anyKept ? next : undefined
}

/** Build an empty row with all column keys set to ''. */
export function emptyRow(
  keys: string[],
): Record<string, unknown> {
  const row: Record<string, unknown> = {}
  for (const k of keys) row[k] = ''
  return row
}

/**
 * Merge the cell at (colKey, startRow) with the cell directly below it.
 * If already a merge, extends it downward by one row.
 * Concatenates cell text with newlines.
 */
export function mergeDown(
  section: TemplateSection,
  colKey: string,
  startRow: number,
  dataRowCount: number,
): TemplateSection {
  if (startRow >= dataRowCount - 1) return section // nothing below to merge

  const merges = section.merges ? cloneMerges(section.merges) : {}
  const list = merges[colKey] ? [...merges[colKey]!] : []

  const existing = list.find(
    (r) => startRow >= r.startRow && startRow < r.startRow + r.span,
  )
  if (existing) {
    // Extend downward — but not past the table end or into the next merge
    const newSpan = Math.min(existing.span + 1, dataRowCount - existing.startRow)
    existing.span = newSpan
  } else {
    list.push({ startRow, span: 2 })
  }

  // Keep sorted & non-overlapping
  list.sort((a, b) => a.startRow - b.startRow)
  merges[colKey] = list

  // Concatenate text into the start row
  const rows = section.rows.map((r) => ({ ...r }))
  const top = String(rows[startRow]?.[colKey] ?? '').trim()
  const below = String(rows[startRow + 1]?.[colKey] ?? '').trim()
  if (rows[startRow]) {
    rows[startRow][colKey] = below ? `${top}\n${below}` : top
  }
  if (rows[startRow + 1]) {
    rows[startRow + 1][colKey] = ''
  }

  return { ...section, rows, merges }
}

/** Split (un-merge) the range covering (colKey, rowIndex). */
export function splitMerge(
  section: TemplateSection,
  colKey: string,
  rowIndex: number,
): TemplateSection {
  if (!section.merges?.[colKey]) return section
  const list = section.merges[colKey].filter(
    (r) => !(rowIndex >= r.startRow && rowIndex < r.startRow + r.span),
  )
  const merges = { ...section.merges }
  if (list.length > 0) {
    merges[colKey] = list
  } else {
    delete merges[colKey]
  }
  return { ...section, merges }
}

function cloneMerges(
  merges: Record<string, CellMerge[]>,
): Record<string, CellMerge[]> {
  const out: Record<string, CellMerge[]> = {}
  for (const [k, v] of Object.entries(merges)) {
    out[k] = v.map((r) => ({ ...r }))
  }
  return out
}
