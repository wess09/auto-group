import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (!location.pathname.startsWith('/login')) {
        location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export type ManagedGroup = {
  id: number
  group_id: number
  name: string
  priority: number
  enabled: boolean
  max_members: number
  current_members: number
  join_url: string
  redirect_message_template: string
  note: string
}

export type AnswerRule = {
  id: number
  name: string
  enabled: boolean
  group_id: number | null
  match_mode: 'contains' | 'exact' | 'regex'
  logic_mode: 'any' | 'all'
  patterns: string[]
}
