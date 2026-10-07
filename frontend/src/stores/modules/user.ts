import { defineStore } from 'pinia'
import { queryClient } from '../../api/queries'
import { pageStates } from '../ui'
import { useTabsStore } from './tabs'

type UserInfo = {
  name: string
}

export const useUserStore = defineStore('geeker-user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    userInfo: {
      name: 'Auto Group',
    } as UserInfo,
  }),
  actions: {
    setToken(token: string) {
      this.token = token
      localStorage.setItem('token', token)
    },
    clearToken() {
      this.token = ''
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
