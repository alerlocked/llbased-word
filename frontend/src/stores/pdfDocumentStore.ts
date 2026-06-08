/**
 * Minimal stub for pdfDocumentStore.
 * Full implementation pending with WASM PDF viewer (#49).
 */
import { create } from 'zustand'

interface TableEntry {
  table_id: string
  [key: string]: unknown
}

interface PdfDocumentState {
  tables: TableEntry[]
  selectedTables: string[]
  updateParserSettings: (settings: Record<string, unknown>) => void
}

export const usePdfDocumentStore = create<PdfDocumentState>()(() => ({
  tables: [],
  selectedTables: [],
  updateParserSettings: () => {},
}))
