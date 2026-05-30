/**
 * Unit tests for processCardParser — the Markdown-to-card segment parser.
 */
import { parseProcessContent } from '../utils/processCardParser'

describe('parseProcessContent', () => {
  // ---------------------------------------------------------------------------
  // Empty / degenerate input
  // ---------------------------------------------------------------------------

  it('returns empty array for empty string', () => {
    expect(parseProcessContent('')).toEqual([])
    expect(parseProcessContent('   ')).toEqual([])
  })

  // ---------------------------------------------------------------------------
  // Pure prose (no process steps)
  // ---------------------------------------------------------------------------

  it('returns single prose segment for non-process markdown', () => {
    const md = '# 普通文档\n\n这是普通内容，没有工序信息。\n'
    const result = parseProcessContent(md)
    expect(result).toHaveLength(1)
    expect(result[0].type).toBe('prose')
    expect(result[0].content).toContain('普通文档')
  })

  // ---------------------------------------------------------------------------
  // Single process step with ## heading
  // ---------------------------------------------------------------------------

  it('parses a single ## 工序N heading', () => {
    const md = [
      '## 工序1：电缆下料',
      '车间：装配车间',
      '1.1 按图纸要求截取电缆',
      '- 热缩管 φ8mm',
      '1.2 剥离绝缘层',
      '检验：1) 尺寸检查 2) 外观检查',
    ].join('\n')

    const result = parseProcessContent(md)
    expect(result).toHaveLength(1)
    expect(result[0].type).toBe('card')
    const cards = result[0].cards!
    expect(cards).toHaveLength(1)
    expect(cards[0].stepNo).toBe('1')
    expect(cards[0].stepName).toBe('电缆下料')
    expect(cards[0].workshop).toBe('装配车间')
    expect(cards[0].subSteps).toHaveLength(2)
    expect(cards[0].subSteps[0].no).toBe('1.1')
    expect(cards[0].subSteps[0].materials).toContain('热缩管 φ8mm')
    expect(cards[0].inspections.length).toBeGreaterThanOrEqual(2)
  })

  // ---------------------------------------------------------------------------
  // Multiple process steps
  // ---------------------------------------------------------------------------

  it('parses multiple consecutive ## 工序N headings', () => {
    const md = [
      '## 工序1：电缆下料',
      '1.1 截取电缆',
      '',
      '## 工序2：安装密封圈',
      '2.1 安装密封圈1',
      '2.2 安装密封圈2',
      '检验：1) 密封圈安装正确',
    ].join('\n')

    const result = parseProcessContent(md)
    expect(result).toHaveLength(1)
    expect(result[0].type).toBe('card')
    const cards = result[0].cards!
    expect(cards).toHaveLength(2)
    expect(cards[0].stepNo).toBe('1')
    expect(cards[1].stepNo).toBe('2')
    expect(cards[1].subSteps).toHaveLength(2)
    expect(cards[1].inspections).toContain('密封圈安装正确')
  })

  // ---------------------------------------------------------------------------
  // ### heading variant
  // ---------------------------------------------------------------------------

  it('parses ### 工序N headings', () => {
    const md = '### 工序3：行程开关安装\n3.1 固定基座\n'
    const result = parseProcessContent(md)
    expect(result).toHaveLength(1)
    expect(result[0].type).toBe('card')
    expect(result[0].cards![0].stepNo).toBe('3')
  })

  // ---------------------------------------------------------------------------
  // Mixed prose + card content
  // ---------------------------------------------------------------------------

  it('separates prose from cards', () => {
    const md = [
      '# 工艺文件目录',
      '',
      '这是目录说明文字。',
      '',
      '## 工序1：电缆下料',
      '1.1 截取电缆',
    ].join('\n')

    const result = parseProcessContent(md)
    // Should have: prose (目录说明) + card (工序1)
    expect(result.length).toBeGreaterThanOrEqual(2)
    const proseSegs = result.filter(s => s.type === 'prose')
    const cardSegs = result.filter(s => s.type === 'card')
    expect(proseSegs.length).toBeGreaterThanOrEqual(1)
    expect(cardSegs.length).toBeGreaterThanOrEqual(1)
    expect(cardSegs[0].cards![0].stepNo).toBe('1')
  })

  // ---------------------------------------------------------------------------
  // --- separator splitting
  // ---------------------------------------------------------------------------

  it('splits by --- separators', () => {
    const md = [
      '## 工序1：电缆下料',
      '1.1 截取电缆',
      '',
      '---',
      '',
      '## 工序2：安装密封圈',
      '2.1 安装密封圈',
    ].join('\n')

    const result = parseProcessContent(md)
    const cards = result.filter(s => s.type === 'card').flatMap(s => s.cards!)
    expect(cards).toHaveLength(2)
  })

  // ---------------------------------------------------------------------------
  // Degradation: non-process heading not parsed as card
  // ---------------------------------------------------------------------------

  it('treats non-process ## headings as prose', () => {
    const md = '## 封面\n封面内容\n\n## 工艺文件目录\n目录内容\n'
    const result = parseProcessContent(md)
    const cardSegs = result.filter(s => s.type === 'card')
    expect(cardSegs).toHaveLength(0) // "封面" and "工艺文件目录" are not process steps
  })

  // ---------------------------------------------------------------------------
  // Real-world: 工序N with colon variants
  // ---------------------------------------------------------------------------

  it('handles both ：and : in process titles', () => {
    const md1 = '## 工序1：电缆下料\n1.1 截取\n'
    const md2 = '## 工序1:电缆下料\n1.1 截取\n'
    const md3 = '## 工序1 电缆下料\n1.1 截取\n'

    for (const md of [md1, md2, md3]) {
      const result = parseProcessContent(md)
      expect(result[0].type).toBe('card')
      expect(result[0].cards![0].stepName).toBe('电缆下料')
    }
  })
})
