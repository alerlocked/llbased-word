import type { TemplateSection } from '../types/template'

export interface CellEdit {
  section_id: string
  section_title: string
  row_key: string
  col_key: string
  col_label: string
  old_value: string
  new_value: string
}

export interface RowChange {
  section_id: string
  section_title: string
  change: 'added' | 'removed'
  row_data: Record<string, unknown>
}

// Candidate business-key columns for row alignment (process docs).
const BUSINESS_KEY_CANDIDATES = ['序号', '工序号', 'step_no', 'seq', 'step', '工序']

function stringify(v: unknown): string {
  if (v === null || v === undefined) return ''
  return String(v)
}

function pickBusinessKey(rows: Record<string, unknown>[]): string | null {
  if (rows.length === 0) return null
  const sample = rows[0]
  for (const k of BUSINESS_KEY_CANDIDATES) {
    if (sample[k] !== undefined && sample[k] !== '') return k
  }
  return null
}

/**
 * Diff original vs current TemplateSection[] → cell edits + row changes.
 * feedback-rules 节点4b.
 *
 * Row alignment: a shared business key (序号/工序号/step_no/...) if both sides
 * have it; otherwise fall back to index — and only do cell-diff when row counts
 * match (avoids shift noise on insert/delete). Count-mismatch without a key is
 * recorded as row add/remove, not cell edits.
 */
export function diffTemplateSections(
  original: TemplateSection[],
  current: TemplateSection[],
): { edits: CellEdit[]; row_changes: RowChange[] } {
  const edits: CellEdit[] = []
  const rowChanges: RowChange[] = []
  const currentById = new Map(current.map((s) => [s.section_id, s]))

  const cellDiffRows = (
    sectionId: string,
    sectionTitle: string,
    o: Record<string, unknown>,
    c: Record<string, unknown>,
    colKeys: string[],
    rowKey: string,
  ) => {
    for (const ck of colKeys) {
      const ov = stringify(o[ck])
      const nv = stringify(c[ck])
      if (ov !== nv) {
        edits.push({ section_id: sectionId, section_title: sectionTitle, row_key: rowKey, col_key: ck, col_label: ck, old_value: ov, new_value: nv })
      }
    }
  }

  for (const origSection of original) {
    const currSection = currentById.get(origSection.section_id)
    if (!currSection) {
      for (const row of origSection.rows) {
        rowChanges.push({ section_id: origSection.section_id, section_title: origSection.title, change: 'removed', row_data: row })
      }
      continue
    }

    const origRows = origSection.rows
    const currRows = currSection.rows
    const colKeys = currSection.column_keys || currSection.columns || []
    const ok = pickBusinessKey(origRows)
    const bizKey = ok && ok === pickBusinessKey(currRows) ? ok : null

    if (bizKey) {
      const origMap = new Map(origRows.map((r) => [stringify(r[bizKey]), r]))
      const currMap = new Map(currRows.map((r) => [stringify(r[bizKey]), r]))
      for (const k of new Set([...origMap.keys(), ...currMap.keys()])) {
        const o = origMap.get(k)
        const c = currMap.get(k)
        if (o && c) {
          cellDiffRows(origSection.section_id, origSection.title, o, c, colKeys, `${bizKey}=${k}`)
        } else if (o) {
          rowChanges.push({ section_id: origSection.section_id, section_title: origSection.title, change: 'removed', row_data: o })
        } else if (c) {
          rowChanges.push({ section_id: currSection.section_id, section_title: currSection.title, change: 'added', row_data: c })
        }
      }
    } else if (origRows.length === currRows.length) {
      for (let i = 0; i < origRows.length; i++) {
        cellDiffRows(origSection.section_id, origSection.title, origRows[i], currRows[i], colKeys, `index=${i}`)
      }
    } else {
      // row count differs + no business key → set-diff rows (avoid shift noise)
      const origSet = new Set(origRows.map((r) => JSON.stringify(r)))
      const currSet = new Set(currRows.map((r) => JSON.stringify(r)))
      for (const r of origRows) if (!currSet.has(JSON.stringify(r))) rowChanges.push({ section_id: origSection.section_id, section_title: origSection.title, change: 'removed', row_data: r })
      for (const r of currRows) if (!origSet.has(JSON.stringify(r))) rowChanges.push({ section_id: currSection.section_id, section_title: currSection.title, change: 'added', row_data: r })
    }
  }

  // sections present in current but not original → all rows added
  const origIds = new Set(original.map((s) => s.section_id))
  for (const currSection of current) {
    if (!origIds.has(currSection.section_id)) {
      for (const row of currSection.rows) {
        rowChanges.push({ section_id: currSection.section_id, section_title: currSection.title, change: 'added', row_data: row })
      }
    }
  }

  return { edits, row_changes: rowChanges }
}
