/**
 * ProcessContentView — mixed rendering container.
 *
 * Splits markdown into card and prose segments, renders cards with
 * <ProcessCard> and prose with markdownToHtml.
 */
import React, { useMemo } from 'react'
import { parseProcessContent } from '../../utils/processCardParser'
import { markdownToHtml } from '../../utils/markdownConverter'
import ProcessCard from './ProcessCard'
import { colors, typography, spacing } from '../../styles/design-tokens'

interface ProcessContentViewProps {
  markdown: string
  className?: string
  style?: React.CSSProperties
}

const ProcessContentView: React.FC<ProcessContentViewProps> = ({
  markdown,
  className,
  style,
}) => {
  const segments = useMemo(() => parseProcessContent(markdown), [markdown])

  if (segments.length === 0) return null

  return (
    <div className={className} style={style}>
      {segments.map((seg, idx) =>
        seg.type === 'card' && seg.cards && seg.cards.length > 0 ? (
          <ProcessCard key={`card-${idx}`} steps={seg.cards} />
        ) : (
          <div
            key={`prose-${idx}`}
            style={{
              lineHeight: typography.lineHeight.relaxed,
              color: colors.textPrimary,
              fontSize: typography.fontSize.base,
              marginBottom: spacing.lg,
            }}
            dangerouslySetInnerHTML={{ __html: markdownToHtml(seg.content) }}
          />
        )
      )}
    </div>
  )
}

export default ProcessContentView
