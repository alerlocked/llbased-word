import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

/**
 * 主题管理Context
 * 支持黑色和白色两种主题切换
 */

export type ThemeType = 'dark' | 'light'

interface ThemeColors {
  // 背景色
  bgPrimary: string
  bgSecondary: string
  bgTertiary: string
  
  // 文本色
  textPrimary: string
  textSecondary: string
  textTertiary: string
  
  // 强调色
  accentPrimary: string
  accentSecondary: string
  
  // 边框色
  borderColor: string
  
  // 渐变色
  gradientPrimary: string
  gradientSecondary: string
}

interface ThemeContextType {
  theme: ThemeType
  colors: ThemeColors
  toggleTheme: () => void
  setTheme: (theme: ThemeType) => void
}

const darkTheme: ThemeColors = {
  // 深色主题 - 蓝白灰配色
  bgPrimary: '#1f1f1f',
  bgSecondary: '#2a2a2a',
  bgTertiary: '#3a3a3a',
  textPrimary: '#ffffff',
  textSecondary: '#d9d9d9',
  textTertiary: '#8c8c8c',
  accentPrimary: '#1890ff',      // 蓝色主色
  accentSecondary: '#40a9ff',    // 浅蓝色
  borderColor: 'rgba(24, 144, 255, 0.3)',
  gradientPrimary: 'linear-gradient(135deg, #1890ff 0%, #40a9ff 50%, #69c0ff 100%)',
  gradientSecondary: 'linear-gradient(90deg, #1890ff 0%, #40a9ff 100%)',
}

const lightTheme: ThemeColors = {
  // 浅色主题 - 蓝白灰配色
  bgPrimary: '#ffffff',
  bgSecondary: '#f5f5f5',
  bgTertiary: '#e8e8e8',
  textPrimary: '#262626',
  textSecondary: '#595959',
  textTertiary: '#8c8c8c',
  accentPrimary: '#1890ff',      // 蓝色主色
  accentSecondary: '#096dd9',    // 深蓝色
  borderColor: '#d9d9d9',
  gradientPrimary: 'linear-gradient(135deg, #096dd9 0%, #1890ff 50%, #40a9ff 100%)',
  gradientSecondary: 'linear-gradient(90deg, #1890ff 0%, #096dd9 100%)',
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export const ThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeType>(() => {
    // 从localStorage读取主题设置
    const savedTheme = localStorage.getItem('app-theme')
    return (savedTheme as ThemeType) || 'light'
  })

  const colors = theme === 'dark' ? darkTheme : lightTheme

  useEffect(() => {
    // 保存主题设置到localStorage
    localStorage.setItem('app-theme', theme)
    
    // 更新CSS变量
    const root = document.documentElement
    root.style.setProperty('--bg-primary', colors.bgPrimary)
    root.style.setProperty('--bg-secondary', colors.bgSecondary)
    root.style.setProperty('--bg-tertiary', colors.bgTertiary)
    root.style.setProperty('--text-primary', colors.textPrimary)
    root.style.setProperty('--text-secondary', colors.textSecondary)
    root.style.setProperty('--text-tertiary', colors.textTertiary)
    root.style.setProperty('--accent-primary', colors.accentPrimary)
    root.style.setProperty('--accent-secondary', colors.accentSecondary)
    root.style.setProperty('--border-color', colors.borderColor)
    root.style.setProperty('--gradient-primary', colors.gradientPrimary)
    root.style.setProperty('--gradient-secondary', colors.gradientSecondary)
  }, [theme, colors])

  const toggleTheme = () => {
    setThemeState(prev => prev === 'dark' ? 'light' : 'dark')
  }

  const setTheme = (newTheme: ThemeType) => {
    setThemeState(newTheme)
  }

  return (
    <ThemeContext.Provider value={{ theme, colors, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

