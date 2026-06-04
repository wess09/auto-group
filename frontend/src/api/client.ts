import axios from 'axios'
import { adminPath } from '../adminRoute'

function apiBaseUrl() {
  const value = import.meta.env.VITE_API_BASE_URL || '/api'
  return value.replace(/\/+$/, '')
}

export const api = axios.create({
  baseURL: apiBaseUrl(),
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
      if (location.hash !== `#${adminPath('login')}`) {
        location.hash = adminPath('login')
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

export type MessageModerationRule = {
  id: number
  name: string
  enabled: boolean
  group_id: number | null
  patterns: string[]
  cloud_review_enabled: boolean
  action: 'recall' | 'mute' | 'recall_and_mute'
  mute_duration_seconds: number
  note: string
}

export type TencentCloudTmsConfig = {
  secret_id: string
  secret_key_configured: boolean
  region: string
  biz_type: string
  source_language: string
  timeout_seconds: number
}

export type JoinBlacklistItem = {
  id: number
  user_id: number
  enabled: boolean
  reason: string
  note: string
}
