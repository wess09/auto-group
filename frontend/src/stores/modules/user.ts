import { defineStore } from 'pinia'

type UserInfo = {
  name: string
}

export const useUserStore = defineStore('geeker-user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    userInfo: {
      name: 'Auto Group'
    } as UserInfo
  }),
  actions: {
    setToken(token: string) {
      this.token = token
      localStorage.setItem('token', token)
    },
    clearToken() {
      this.token = ''
      localStorage.removeItem('token')
    }
  }
})
