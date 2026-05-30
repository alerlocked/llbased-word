/**
 * Process Card Parser — parse Markdown into structured process card segments.
 *
 * Detects "process step" blocks (工序/工步/辅料/检验) and separates them
 * from regular prose.  Anything that fails to parse gracefully falls back
 * to prose so the display is never broken.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SubStep {
  no: string        // "1.1"
  content: string   // "按图纸要求截取电缆..."
  materials: string[]  // ["辅料A", "工具B"]
}

export interface ProcessStep {
  stepNo: string      // "1"
  stepName: string    // "电缆下料"
  workshop: string    // "装配车间"
  subSteps: SubStep[]
  inspections: string[]
}

export interface ContentSegment {
  type: 'card' | 'prose'
  content: string         // prose: original Markdown
  cards?: ProcessStep[]   // card: parsed process data
}

// ---------------------------------------------------------------------------
// Regex helpers
// ---------------------------------------------------------------------------

// Matches Markdown heading + process title:
//   "## 工序1 电缆下料", "### 工序1：电缆下料", "工序1 电缆下料"
const PROCESS_TITLE_RE = /^#{0,3}\s*工序\s*(\d+)\s*[：:\s]\s*(.*)/

// Matches lines like "车间：装配车间" or "车间: 装配车间"
const WORKSHOP_RE = /^车间\s*[：:]\s*(.+)/

// Matches sub-step numbers like "1.1" or "2.3"
const SUBSTEP_RE = /^(\d+\.\d+)\s+(.*)/

// Matches material/tool lines like "- 热缩管 φ8mm"
const MATERIAL_RE = /^[-–—]\s+(.*)/

// ---------------------------------------------------------------------------
// Internal: strip leading markdown heading markers
// ---------------------------------------------------------------------------

function stripHeading(line: string): string {
  return line.replace(/^#{1,6}\s*/, '')
}

// ---------------------------------------------------------------------------
// Internal parser for a single process step block
// ---------------------------------------------------------------------------

function parseSingleStep(block: string): ProcessStep | null {
  const lines = block.split('\n')
  if (lines.length === 0) return null

  // Extract title (first non-empty line, after stripping heading markers)
  let titleLine = ''
  let startIdx = 0
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim()
    if (trimmed) {
      titleLine = stripHeading(trimmed)
      startIdx = i + 1
      break
    }
  }

  const titleMatch = PROCESS_TITLE_RE.exec(titleLine)
  if (!titleMatch) return null

  const stepNo = titleMatch[1]
  const stepName = titleMatch[2].trim()

  let workshop = ''
  const subSteps: SubStep[] = []
  const inspections: string[] = []

  let currentSubStep: SubStep | null = null
  let inInspection = false

  for (let i = startIdx; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    // Workshop
    const wsMatch = WORKSHOP_RE.exec(line)
    if (wsMatch) {
      workshop = wsMatch[1].trim()
      continue
    }

    // Inspection section start
    if (/^检验/.test(stripHeading(line))) {
      inInspection = true
      const rest = line.replace(/^#{0,3}\s*检验\s*[：:]*\s*/, '')
      if (rest) {
        extractInspections(rest, inspections)
      }
      continue
    }

    if (inInspection) {
      extractInspections(line, inspections)
      continue
    }

    // Sub-step
    const subMatch = SUBSTEP_RE.exec(line)
    if (subMatch) {
      currentSubStep = {
        no: subMatch[1],
        content: subMatch[2].trim(),
        materials: []
      }
      subSteps.push(currentSubStep)
      continue
    }

    // Material line — attach to current sub-step
    const matMatch = MATERIAL_RE.exec(line)
    if (matMatch && currentSubStep) {
      currentSubStep.materials.push(matMatch[1].trim())
      continue
    }

    // Continuation text — append to current sub-step content
    if (currentSubStep) {
      currentSubStep.content += ' ' + line
    }
  }

  return { stepNo, stepName, workshop, subSteps, inspections }
}

function extractInspections(text: string, out: string[]) {
  // Try numbered items like "1) xxx 2) yyy"
  const items = text.split(/\s*\d+[)）]\s*/).filter(Boolean)
  if (items.length > 0) {
    out.push(...items.map(s => s.trim()).filter(Boolean))
    return
  }
  // Fallback: whole line
  const trimmed = text.trim()
  if (trimmed) out.push(trimmed)
}

// ---------------------------------------------------------------------------
// Block splitting
// ---------------------------------------------------------------------------

/**
 * Check if a line is a process step heading.
 * Accepts: "工序1：电缆下料", "## 工序1 电缆下料", "### 工序1：电缆下料"
 */
function isProcessTitleLine(line: string): boolean {
  return PROCESS_TITLE_RE.test(stripHeading(line.trim()))
}

/**
 * Split markdown text into blocks where each block starts at a process title
 * or is a prose section between process titles.
 */
function splitIntoBlocks(text: string): string[] {
  const lines = text.split('\n')
  const blocks: string[] = []
  let currentBlockLines: string[] = []

  const flushBlock = () => {
    if (currentBlockLines.length > 0) {
      blocks.push(currentBlockLines.join('\n'))
      currentBlockLines = []
    }
  }

  for (const line of lines) {
    if (isProcessTitleLine(line) && currentBlockLines.length > 0) {
      // Found a new process title — flush previous block
      flushBlock()
    }
    currentBlockLines.push(line)
  }

  flushBlock()
  return blocks.filter(b => b.trim())
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Parse a full Markdown string into an array of ContentSegments.
 *
 * Strategy:
 *   1. First try splitting by `---` (orchestrator section separators)
 *   2. Within each section, split again by process title lines
 *   3. Process title blocks → parse into ProcessStep
 *   4. Everything else → prose
 *   5. Parse failures gracefully degrade to prose
 */
export function parseProcessContent(markdown: string): ContentSegment[] {
  if (!markdown || !markdown.trim()) return []

  const segments: ContentSegment[] = []
  let currentCards: ProcessStep[] = []
  let currentProse = ''

  const flushCards = () => {
    if (currentCards.length > 0) {
      segments.push({ type: 'card', content: '', cards: [...currentCards] })
      currentCards = []
    }
  }

  const flushProse = () => {
    if (currentProse.trim()) {
      segments.push({ type: 'prose', content: currentProse.trim() })
      currentProse = ''
    }
  }

  // Step 1: split by --- separators (orchestrator generated content)
  const sections = markdown.split(/\n\n---\n\n|\n---\n/).filter(s => s.trim())

  for (const section of sections) {
    // Step 2: within each section, split by process title lines
    const blocks = splitIntoBlocks(section)

    for (const block of blocks) {
      const trimmed = block.trim()
      if (!trimmed) continue

      // Check if this block starts with a process title
      const firstLine = trimmed.split('\n')[0] ?? ''
      if (isProcessTitleLine(firstLine)) {
        flushProse()
        const step = parseSingleStep(trimmed)
        if (step) {
          currentCards.push(step)
        } else {
          // Parse failed — degrade to prose
          flushCards()
          currentProse += trimmed + '\n\n'
        }
      } else {
        flushCards()
        currentProse += trimmed + '\n\n'
      }
    }
  }

  flushCards()
  flushProse()

  return segments
}
