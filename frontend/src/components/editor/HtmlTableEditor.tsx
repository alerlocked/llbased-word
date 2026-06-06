/**
 * HtmlTableEditor — Renders VLM HTML tables with contentEditable cells
 *
 * - Header rows: grey background, locked
 * - Data rows: white background, editable textContent
 * - Signature rows: hidden
 * - Auto-saves on blur with debounce
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { Spin, Empty } from 'antd'
import { parseVlmHtml, classifyRow, type TablePage, type RowKind } from '../../utils/htmlTableParser'
import '../../styles/html-table-editor.css'

interface Props {
  projectId: number | null
  /** Callback with the full HTML when content changes */
  onSave: (html: string) => void
  /** Initial HTML content (from store) */
  value: string
  /** Called when internal content changes (to update store) */
  onChange: (html: string) => void
}

const API_BASE = 'http://localhost:8000/api/creation'

const HtmlTableEditor: React.FC<Props> = ({ projectId, onSave, value, onChange }) => {
  const [pages, setPages] = useState<TablePage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Track whether we've loaded VLM HTML at least once
  const vlmLoadedRef = useRef(false)

  // Load VLM HTML on mount or project change
  useEffect(() => {
    if (!projectId) {
      setPages([])
      vlmLoadedRef.current = false
      return
    }

    // If store already has HTML table content, use it
    if (value && /<table/i.test(value)) {
      const parsed = parseVlmHtml(value)
      setPages(parsed)
      vlmLoadedRef.current = true
      return
    }

    // Otherwise fetch VLM HTML from backend
    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(`${API_BASE}/projects/${projectId}/vlm-html`)
      .then(res => {
        if (res.status === 404) return null
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(data => {
        if (cancelled) return
        setLoading(false)
        if (!data || !data.html) {
          setError('no_vlm_html')
          return
        }
        const parsed = parseVlmHtml(data.html)
        setPages(parsed)
        onChange(data.html)
        vlmLoadedRef.current = true
      })
      .catch(err => {
        if (cancelled) return
        setLoading(false)
        setError(err.message)
      })

    return () => { cancelled = true }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced save on content change
  const scheduleSave = useCallback((html: string) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      onSave(html)
    }, 500)
  }, [onSave])

  // Extract HTML from all rendered tables in the container
  const collectHtml = useCallback(() => {
    if (!containerRef.current) return value
    const tables = containerRef.current.querySelectorAll('.vlm-page-table')
    if (tables.length === 0) return value

    const parts: string[] = []
    tables.forEach((table, idx) => {
      if (pages.length > 1) {
        parts.push(`## 第 ${idx + 1} 页`)
      }
      parts.push(table.outerHTML)
    })
    return parts.join('\n')
  }, [value, pages.length])

  // Handle cell blur — update store and trigger debounced save
  const handleCellBlur = useCallback(() => {
    const html = collectHtml()
    if (html !== value) {
      onChange(html)
      scheduleSave(html)
    }
  }, [collectHtml, value, onChange, scheduleSave])

  // Render a single table page
  const renderTable = (page: TablePage, pageIdx: number) => {
    return (
      <div key={`page-${pageIdx}`} className="vlm-page-container">
        {pages.length > 1 && (
          <div className="vlm-page-label">第 {page.pageNumber} 页</div>
        )}
        <div
          className="vlm-page-table"
          dangerouslySetInnerHTML={{ __html: page.rawHtml }}
          ref={(el) => {
            if (!el) return
            // Post-process: classify rows and set editability
            const rows = el.querySelectorAll('tr')
            rows.forEach(tr => {
              const kind = classifyRow(tr as HTMLTableRowElement)
              const tds = tr.querySelectorAll('td, th')

              if (kind === 'signature') {
                // Hide signature rows
                ;(tr as HTMLElement).style.display = 'none'
              } else if (kind === 'header') {
                // Lock header cells
                tds.forEach(td => {
                  const el = td as HTMLElement
                  el.classList.add('locked')
                  el.removeAttribute('contenteditable')
                })
              } else {
                // Make data cells editable
                tds.forEach(td => {
                  const el = td as HTMLElement
                  el.setAttribute('contenteditable', 'true')
                  el.classList.add('editable')
                })
              }
            })
          }}
          onBlur={handleCellBlur}
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200 }}>
        <Spin tip="加载表格..." />
      </div>
    )
  }

  if (error === 'no_vlm_html') {
    return (
      <Empty description="该项目暂无 VLM 解析表格" />
    )
  }

  if (error) {
    return (
      <Empty description={`加载失败: ${error}`} />
    )
  }

  if (pages.length === 0) {
    return null
  }

  return (
    <div ref={containerRef} className="vlm-table-editor">
      {pages.map((page, idx) => renderTable(page, idx))}
    </div>
  )
}

export default HtmlTableEditor
