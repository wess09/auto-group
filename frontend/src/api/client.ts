import axios from 'axios'
import { adminPath } from '../adminRoute'
import { SocketClient, websocketUrl } from './socket'

export const api = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, ''),
  timeout: 30000,
})
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
export const socket = new SocketClient(
  () =>
    websocketUrl(
      import.meta.env.VITE_API_BASE_URL || '/api',
      import.meta.env.VITE_WS_BASE_URL,
      location.href,
    ),
  () => localStorage.getItem('token') || '',
)
export function getApiErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    return typeof detail === 'string' ? detail : error.message
  }
  return error instanceof Error ? error.message : '请求失败'
}
export function expireLogin() {
  socket.close()
  localStorage.removeItem('token')
  window.dispatchEvent(new Event('auth-expired'))
  location.hash = adminPath('login')
}
socket.onAuthExpired = expireLogin
window.addEventListener('storage', (event) => {
  if (event.key === 'token' && !event.newValue) expireLogin()
})
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !String(error.config?.url).includes('/auth/login'))
      expireLogin()
    return Promise.reject(error)
  },
)
