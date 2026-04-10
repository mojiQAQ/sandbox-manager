import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器：统一错误处理
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const msg = error.response.data?.message || error.response.data?.detail || '请求失败'
      console.error(`[API] ${error.response.status}: ${msg}`)
    } else if (error.request) {
      console.error('[API] 无法连接到服务器')
    }
    return Promise.reject(error)
  },
)

export default client
