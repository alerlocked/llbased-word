/**
 * Design Tokens - 设计系统变量
 * 白色系简洁风格，参考图片背景色
 */

// 颜色系统
export const colors = {
  // 主色 - 温暖黄（保留用于强调）
  primary: '#F5A623',
  primaryHover: '#E6991A',
  primaryActive: '#D18915',
  primaryLight: '#FFF4E0',
  
  // 辅助色
  secondary: '#1F1F1F',
  secondaryLight: '#4A4A4A',
  
  // 背景色 - 白色系
  bgPrimary: '#FFFFFF',      // 纯白背景
  bgSecondary: '#FAFAFA',    // 浅灰背景，用于卡片等
  bgTertiary: '#F5F5F5',     // 更浅的灰，用于hover状态
  
  // 强调色
  accent: '#FF6B35',
  accentLight: '#FFE8E0',
  
  // 文字色
  textPrimary: '#1F1F1F',
  textSecondary: '#666666',
  textTertiary: '#999999',
  textInverse: '#FFFFFF',
  
  // 边框色 - 浅灰色系
  border: '#E8E8E8',
  borderLight: '#D9D9D9',
  
  // 状态色
  success: '#52C41A',
  warning: '#FAAD14',
  error: '#FF4D4F',
  info: '#1890FF',
  
  // 特殊
  overlay: 'rgba(31, 31, 31, 0.6)',
  shadow: 'rgba(0, 0, 0, 0.08)'
}

// 圆角系统
export const radius = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '20px',
  xxl: '24px',
  full: '9999px'
}

// 间距系统
export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  xxl: '32px',
  xxxl: '48px'
}

// 字体系统
export const typography = {
  // 字体族
  fontFamily: {
    base: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif',
    display: '"Playfair Display", Georgia, serif',  // 标题展示字体
    mono: 'Menlo, Monaco, "Courier New", monospace'
  },
  
  // 字号
  fontSize: {
    xs: '12px',
    sm: '13px',
    base: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
    xxl: '24px',
    xxxl: '32px',
    display: '48px'
  },
  
  // 行高
  lineHeight: {
    tight: 1.25,
    base: 1.5,
    relaxed: 1.75,
    loose: 2
  },
  
  // 字重
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700
  }
}

// 阴影系统
export const shadows = {
  none: 'none',
  sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
  base: '0 2px 8px rgba(0, 0, 0, 0.08)',
  md: '0 4px 16px rgba(0, 0, 0, 0.1)',
  lg: '0 8px 24px rgba(0, 0, 0, 0.12)',
  xl: '0 16px 48px rgba(0, 0, 0, 0.16)',
  inner: 'inset 0 2px 4px rgba(0, 0, 0, 0.06)'
}

// 动画系统
export const animation = {
  duration: {
    fast: '0.15s',
    base: '0.25s',
    slow: '0.35s',
    slower: '0.5s'
  },
  easing: {
    ease: 'ease',
    easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
    easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
    easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
    spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)'
  }
}

// 断点
export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  xxl: '1536px'
}

// Z-index 层级
export const zIndex = {
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modalBackdrop: 1040,
  modal: 1050,
  popover: 1060,
  tooltip: 1070
}

// 导出完整 theme 对象
export const theme = {
  colors,
  radius,
  spacing,
  typography,
  shadows,
  animation,
  breakpoints,
  zIndex
}

export default theme

