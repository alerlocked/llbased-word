/**
 * Card - 统一卡片组件
 * 温暖风格，柔和阴影
 */
import { HTMLAttributes, ReactNode } from 'react'
import { colors, radius, shadows, spacing } from '../../styles/design-tokens'

type CardVariant = 'default' | 'elevated' | 'outlined' | 'glass'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hoverable?: boolean
  children?: ReactNode
}

const variantStyles: Record<CardVariant, React.CSSProperties> = {
  default: {
    background: colors.bgSecondary,
    boxShadow: shadows.base,
    border: 'none'
  },
  elevated: {
    background: colors.bgSecondary,
    boxShadow: shadows.md,
    border: 'none'
  },
  outlined: {
    background: colors.bgSecondary,
    boxShadow: 'none',
    border: `1px solid ${colors.border}`
  },
  glass: {
    background: 'rgba(255, 255, 255, 0.8)',
    backdropFilter: 'blur(10px)',
    boxShadow: shadows.base,
    border: `1px solid ${colors.borderLight}`
  }
}

const paddingStyles: Record<'none' | 'sm' | 'md' | 'lg', string> = {
  none: '0',
  sm: spacing.md,
  md: spacing.lg,
  lg: spacing.xl
}

const WarmCard: React.FC<CardProps> = ({
  variant = 'default',
  padding = 'md',
  hoverable = false,
  children,
  style,
  ...props
}) => {
  const baseStyle: React.CSSProperties = {
    borderRadius: radius.lg,
    padding: paddingStyles[padding],
    transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
    ...variantStyles[variant],
    ...style
  }

  return (
    <div
      style={baseStyle}
      onMouseEnter={(e) => {
        if (hoverable) {
          e.currentTarget.style.transform = 'translateY(-4px)'
          e.currentTarget.style.boxShadow = shadows.lg
        }
      }}
      onMouseLeave={(e) => {
        if (hoverable) {
          e.currentTarget.style.transform = 'translateY(0)'
          e.currentTarget.style.boxShadow = variantStyles[variant].boxShadow as string
        }
      }}
      {...props}
    >
      {children}
    </div>
  )
}

/**
 * CardHeader - 卡片头部
 */
interface CardHeaderProps {
  title: ReactNode
  extra?: ReactNode
  divider?: boolean
}

export const CardHeader: React.FC<CardHeaderProps> = ({ title, extra, divider = true }) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: divider ? spacing.md : 0,
    paddingBottom: divider ? spacing.md : 0,
    borderBottom: divider ? `1px solid ${colors.borderLight}` : 'none'
  }}>
    <div style={{ fontWeight: 600, fontSize: 16, color: colors.textPrimary }}>
      {title}
    </div>
    {extra && <div>{extra}</div>}
  </div>
)

/**
 * CardBody - 卡片内容区
 */
export const CardBody: React.FC<{ children: ReactNode }> = ({ children }) => (
  <div style={{ color: colors.textPrimary }}>
    {children}
  </div>
)

/**
 * CardFooter - 卡片底部
 */
interface CardFooterProps {
  children: ReactNode
  divider?: boolean
  align?: 'left' | 'center' | 'right'
}

export const CardFooter: React.FC<CardFooterProps> = ({ 
  children, 
  divider = true,
  align = 'right'
}) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: align === 'left' ? 'flex-start' : align === 'center' ? 'center' : 'flex-end',
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingTop: divider ? spacing.md : 0,
    borderTop: divider ? `1px solid ${colors.borderLight}` : 'none'
  }}>
    {children}
  </div>
)

export { WarmCard }
export default WarmCard


