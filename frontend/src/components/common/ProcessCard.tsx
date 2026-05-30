/**
 * ProcessCard — renders assembly process steps as structured cards.
 *
 * Layout per step:
 *   Header  — step number, name, workshop
 *   Body    — left: sub-steps, right: materials/tools (2fr 1fr grid)
 *   Footer  — inspection items
 */
import React from 'react'
import { colors, radius, spacing, typography, shadows } from '../../styles/design-tokens'
import type { ProcessStep } from '../../utils/processCardParser'

interface ProcessCardProps {
  steps: ProcessStep[]
}

const ProcessCard: React.FC<ProcessCardProps> = ({ steps }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      {steps.map((step) => (
        <div
          key={step.stepNo}
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.sm,
            overflow: 'hidden',
            boxShadow: shadows.sm,
            background: colors.bgPrimary,
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: `${spacing.sm} ${spacing.lg}`,
              background: colors.primaryLight,
              borderBottom: `1px solid ${colors.borderLight}`,
            }}
          >
            <span style={{
              fontWeight: typography.fontWeight.semibold,
              fontSize: typography.fontSize.md,
              color: colors.textPrimary,
            }}>
              工序{step.stepNo}: {step.stepName}
            </span>
            {step.workshop && (
              <span style={{
                fontSize: typography.fontSize.sm,
                color: colors.textSecondary,
              }}>
                车间: {step.workshop}
              </span>
            )}
          </div>

          {/* Body — sub-steps + materials */}
          {step.subSteps.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr',
                minHeight: 60,
              }}
            >
              {/* Left: sub-steps */}
              <div
                style={{
                  padding: spacing.lg,
                  borderRight: `1px solid ${colors.borderLight}`,
                }}
              >
                {step.subSteps.map((ss) => (
                  <div
                    key={ss.no}
                    style={{
                      marginBottom: spacing.sm,
                      lineHeight: typography.lineHeight.relaxed,
                      fontSize: typography.fontSize.base,
                      color: colors.textPrimary,
                    }}
                  >
                    <span style={{
                      fontWeight: typography.fontWeight.semibold,
                      color: colors.primary,
                      marginRight: spacing.sm,
                    }}>
                      {ss.no}
                    </span>
                    {ss.content}
                  </div>
                ))}
              </div>

              {/* Right: materials/tools */}
              <div style={{ padding: spacing.lg }}>
                {(() => {
                  // Collect all materials across sub-steps
                  const allMaterials = step.subSteps.flatMap(ss => ss.materials)
                  if (allMaterials.length === 0) return null
                  return (
                    <div>
                      <div style={{
                        fontSize: typography.fontSize.xs,
                        color: colors.textTertiary,
                        marginBottom: spacing.xs,
                        fontWeight: typography.fontWeight.medium,
                      }}>
                        辅助材料 / 仪器装备
                      </div>
                      {allMaterials.map((m, i) => (
                        <div
                          key={i}
                          style={{
                            fontSize: typography.fontSize.sm,
                            color: colors.textSecondary,
                            lineHeight: typography.lineHeight.relaxed,
                            paddingLeft: spacing.sm,
                            borderLeft: `2px solid ${colors.primaryLight}`,
                            marginBottom: 4,
                          }}
                        >
                          {m}
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </div>
            </div>
          )}

          {/* Inspection footer */}
          {step.inspections.length > 0 && (
            <div
              style={{
                padding: `${spacing.sm} ${spacing.lg}`,
                borderTop: `1px solid ${colors.borderLight}`,
                background: colors.bgSecondary,
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: spacing.md,
              }}
            >
              <span style={{
                fontSize: typography.fontSize.xs,
                fontWeight: typography.fontWeight.semibold,
                color: colors.textTertiary,
                flexShrink: 0,
              }}>
                检验:
              </span>
              {step.inspections.map((insp, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: typography.fontSize.sm,
                    color: colors.textSecondary,
                  }}
                >
                  {i + 1}) {insp}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default ProcessCard
