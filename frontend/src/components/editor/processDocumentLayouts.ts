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
  return LAYOUTS[chapterCode]
}
