/**
 * Button - 统一按钮组件
 * 温暖黄色系风格，支持多种变体
 */
import { ButtonHTMLAttributes, ReactNode } from 'react'
import { colors, radius, animation } from '../../styles/design-tokens'

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'text'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: ReactNode
  iconPosition?: 'left' | 'right'
  loading?: boolean
  block?: boolean
  children?: ReactNode
}

const sizeStyles: Record<ButtonSize, React.CSSProperties> = {
  sm: {
    padding: '6px 16px',
    fontSize: '13px',
    height: '32px'
  },
  md: {
    padding: '10px 24px',
    fontSize: '14px',
    height: '40px'
  },
  lg: {
    padding: '14px 32px',
    fontSize: '16px',
    height: '48px'
  }
}

const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: colors.primary,
    color: colors.textPrimary,
    border: 'none'
  },
  secondary: {
    background: colors.bgSecondary,
    color: colors.textPrimary,
    border: `1px solid ${colors.border}`
  },
  outline: {
    background: 'transparent',
    color: colors.textPrimary,
    border: `2px solid ${colors.border}`
  },
  ghost: {
    background: colors.primaryLight,
    color: colors.primary,
    border: 'none'
  },
  text: {
    background: 'transparent',
    color: colors.textSecondary,
    border: 'none'
  }
}

const WarmButton: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'left',
  loading = false,
  block = false,
  children,
  disabled,
  style,
  ...props
}) => {
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    borderRadius: radius.xl,
    fontWeight: 500,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    transition: `all ${animation.duration.base} ${animation.easing.spring}`,
    outline: 'none',
    opacity: disabled ? 0.5 : 1,
    width: block ? '100%' : 'auto',
    ...sizeStyles[size],
    ...variantStyles[variant],
    ...style
  }

  return (
    <button
      style={baseStyle}
      disabled={disabled || loading}
      onMouseEnter={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.transform = 'translateY(-2px)'
          if (variant === 'primary') {
            e.currentTarget.style.background = colors.primaryHover
          } else if (variant === 'secondary' || variant === 'outline') {
            e.currentTarget.style.background = colors.bgTertiary
          } else if (variant === 'text') {
            e.currentTarget.style.background = colors.bgTertiary
          }
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.background = variantStyles[variant].background as string
      }}
      onMouseDown={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.transform = 'translateY(0) scale(0.98)'
        }
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px) scale(1)'
      }}
      {...props}
    >
      {loading && (
        <span style={{
          width: 16,
          height: 16,
          border: '2px solid currentColor',
          borderTopColor: 'transparent',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }} />
      )}
      {!loading && icon && iconPosition === 'left' && icon}
      {children}
      {!loading && icon && iconPosition === 'right' && icon}
      
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </button>
  )
}

export default WarmButton


