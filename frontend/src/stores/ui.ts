import { ref } from 'vue'

export const toast = ref({ open: false, text: '', color: 'primary' })
export function notify(text: string, color = 'primary') {
  toast.value = { open: true, text, color }
}
export function report(error: unknown) {
  notify(error instanceof Error ? error.message : '操作失败', 'error')
}
export type PageState = {
  page: number
  search: string
  group?: number
  tab?: string
  jobId?: number
  startDate?: string
  endDate?: string
  folders?: { id: string; name: string }[]
}
class PageStateCache extends Map<string, PageState> {
  override set(key: string, value: PageState) {
    // A leaving page may unmount after logout has cleared state.
    if (localStorage.getItem('token')) super.set(key, value)
    return this
  }
}
export const pageStates = new PageStateCache()
