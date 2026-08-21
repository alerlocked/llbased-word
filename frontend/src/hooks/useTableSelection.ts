/**
 * useTableSelection — detect text selection inside contentEditable table cells.
 *
 * Parallel to useSelection (which is Tiptap-only). This hook listens to
 * native `mouseup` / `selectionchange` on a container ref and reads
 * `window.getSelection()` to capture highlighted text in `<td contentEditable>`.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { CellInfo } from '../types/template'

export interface TableSelectionInfo {
  text: string
  cellInfo: CellInfo
  originalLength: number
  isTruncated: boolean
}

export interface TableSelectionPosition {
  top: number
  left: number
  width: number
  height: number
}

interface UseTableSelectionOptions {
  /** Max characters to capture; excess is truncated. Default 500. */
  maxLength?: number
  /** Debounce delay in ms. Default 150. */
  debounceMs?: number
}

interface UseTableSelectionReturn {
  selection: TableSelectionInfo | null
  position: TableSelectionPosition | null
  isVisible: boolean
}

/**
 * Walk up from a node to find the enclosing <tr data-row-index> and
 * <td data-col-key>, then extract row/col identifiers.
 */
function extractCellInfo(
  node: Node | null,
  sectionIndex: number,
): CellInfo | null {
  if (!node) return null
  let el: HTMLElement | null =
    node.nodeType === Node.TEXT_NODE
      ? (node.parentElement as HTMLElement | null)
      : (node as HTMLElement)

  // Find enclosing <td>
  let td: HTMLElement | null = null
  while (el && el.tagName !== 'TD') {
    el = el.parentElement
  }
  td = el
  if (!td) return null

  const colKey = td.getAttribute('data-col-key')
  if (!colKey) return null

  // Find enclosing <tr>
  let tr: HTMLElement | null = td.parentElement
  while (tr && tr.tagName !== 'TR') {
    tr = tr.parentElement
  }
  if (!tr) return null

  const rowIndexAttr = tr.getAttribute('data-row-index')
  if (rowIndexAttr === null) return null

  return {
    sectionIndex,
    rowIndex: parseInt(rowIndexAttr, 10),
    colKey,
  }
}

export function useTableSelection(
  containerRef: React.RefObject<HTMLElement | null>,
  sectionIndex: number,
  options: UseTableSelectionOptions = {},
): UseTableSelectionReturn {
  const { maxLength = 200, debounceMs = 150 } = options
  const [selection, setSelection] = useState<TableSelectionInfo | null>(null)
  const [position, setPosition] = useState<TableSelectionPosition | null>(null)
  const [isVisible, setIsVisible] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const checkSelection = useCallback(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }

    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
      setSelection(null)
      setIsVisible(false)
      return
    }

    const range = sel.getRangeAt(0)
    const text = sel.toString().trim()
    if (!text) {
      setSelection(null)
      setIsVisible(false)
      return
    }

    // Verify selection is inside our container
    const container = containerRef.current
    if (!container) return
    if (!container.contains(range.commonAncestorContainer)) {
      setSelection(null)
      setIsVisible(false)
      return
    }

    // Extract cell info
    const cellInfo = extractCellInfo(range.commonAncestorContainer, sectionIndex)
    if (!cellInfo) {
      setSelection(null)
      setIsVisible(false)
      return
    }

    // Truncate to maxLength
    const isTruncated = text.length > maxLength
    const truncated = isTruncated ? text.slice(0, maxLength) : text

    // Compute selection box position + dimensions from range rect
    const rect = range.getBoundingClientRect()

    setSelection({ text: truncated, cellInfo, originalLength: text.length, isTruncated })
    setPosition({
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    })
    setIsVisible(true)
  }, [containerRef, sectionIndex, maxLength])

  const debouncedCheck = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(checkSelection, debounceMs)
  }, [checkSelection, debounceMs])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleMouseUp = () => debouncedCheck()
    const handleSelectionChange = () => debouncedCheck()

    container.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('selectionchange', handleSelectionChange)

    return () => {
      container.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('selectionchange', handleSelectionChange)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
    }
  }, [containerRef, debouncedCheck])

  return { selection, position, isVisible }
}
