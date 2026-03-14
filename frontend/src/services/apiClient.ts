/**
 * 统一的API客户端
 * 提供统一的axios实例和错误处理
 */
import axios from 'axios'
import { message } from 'antd'

// 创建axios实例
const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 300000, // 5分钟超时
})

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 提取错误信息
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败'
    
    // 显示错误提示
    message.error(errorMsg)
    
    // 记录错误日志
    console.error('API请求失败:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      message: errorMsg
    })
    
    return Promise.reject(error)
  }
)

export default apiClient

