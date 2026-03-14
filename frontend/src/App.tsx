import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import WorkspacePage from './pages/WorkspacePage'

/**
 * 应用主组件
 * 工艺文件辅助编辑系统 - 单页面工作台
 */
function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* 主工作台 - 工艺文件辅助编辑 */}
          <Route path="/" element={<WorkspacePage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App












