import { defineStore } from 'pinia'
import { queryClient } from '../../api/queries'
import { pageStates } from '../ui'
import { useTabsStore } from './tabs'
import { appName } from '../../branding'
import { api } from '../../api/client'
import type { AdminProfile } from '../../api/types'

type UserInfo = {
  name: string
}

export const useUserStore = defineStore('geeker-user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    profile: null as AdminProfile | null,
    profileToken: '',
    userInfo: {
      name: appName,
    } as UserInfo,
  }),
  getters: {
    isSuperadmin: (state) => state.profile?.role === 'superadmin',
  },
  actions: {
    async loadProfile() {
      if (this.profile && this.profileToken === this.token) return this.profile
      const token = this.token
      const { data } = await api.get<AdminProfile>('/auth/me')
      if (this.token === token) {
        this.profile = data
        this.profileToken = token
        this.userInfo.name = data.display_name || data.username
      }
      return data
    },
    setToken(token: string) {
      this.token = token
      this.profile = null
      this.profileToken = ''
      localStorage.setItem('token', token)
    },
    clearToken() {
      this.token = ''
      this.profile = null
      this.profileToken = ''
      this.userInfo.name = appName
      localStorage.removeItem('token')
    },
  },
})

window.addEventListener('auth-expired', () => {
  useUserStore().clearToken()
  queryClient.clear()
  pageStates.clear()
  useTabsStore().tabs = []
})
