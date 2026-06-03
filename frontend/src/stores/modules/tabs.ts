import { defineStore } from 'pinia'

export type WorkTab = {
  path: string
  title: string
  affix?: boolean
}

export const useTabsStore = defineStore('geeker-tabs', {
  state: () => ({
    tabs: [] as WorkTab[]
  }),
  actions: {
    addTab(tab: WorkTab) {
      if (this.tabs.some((item) => item.path === tab.path)) return
      this.tabs.push(tab)
    },
    removeTab(path: string) {
      const next = this.tabs.filter((item) => item.affix || item.path !== path)
      this.tabs = next.length ? next : this.tabs.filter((item) => item.affix)
    }
  }
})
