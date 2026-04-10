import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import WorkspacePage from './pages/WorkspacePage'
import ProfilePage from './pages/ProfilePage'

/**
 * 应用主组件
 * 工艺文件辅助编辑系统 - 单页面工作台
 */
function App() {
  return (
    <ThemeProvider>
      <BrowserRouter future={{ v7_startTransition: true }}>
        <Routes future={{ v7_relativeSplatPath: true }}>
          {/* 主工作台 - 工艺文件辅助编辑 */}
          <Route path="/" element={<WorkspacePage />} />
          {/* 用户画像管理 */}
          <Route path="/profile" element={<ProfilePage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App












