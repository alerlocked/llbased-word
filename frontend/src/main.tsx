import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import App from './App'
import './index.css'
import './styles/global.css'

// 配置dayjs为中文
dayjs.locale('zh-cn')

// 应用入口文件
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* Ant Design配置为中文 */}
    <ConfigProvider locale={zhCN}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
























