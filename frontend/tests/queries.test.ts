import { afterEach, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { queryClient, useRpcQuery, visible } from '../src/api/queries'
import { socket } from '../src/api/client'
import { createMaterialTheme } from '../src/theme/dynamicTheme'
import { pageStates } from '../src/stores/ui'
import { useResourceDetail } from '../src/api/details'

afterEach(() => {
  queryClient.clear()
  vi.restoreAllMocks()
  visible.value = true
  localStorage.removeItem('token')
  pageStates.clear()
})
it('deduplicates matching queries and reuses a fresh cached page', async () => {
  const read = vi
    .spyOn(socket, 'read')
    .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 })
  const component = defineComponent({
    setup() {
      useRpcQuery('groups.list', {}, 'groups')
      useRpcQuery('groups.list', {}, 'groups')
      return () => h('div')
    },
  })
  const first = mount(component, { global: { plugins: [[VueQueryPlugin, { queryClient }]] } })
  await flushPromises()
  expect(read).toHaveBeenCalledTimes(1)
  first.unmount()
  const second = mount(component, { global: { plugins: [[VueQueryPlugin, { queryClient }]] } })
  await flushPromises()
  expect(read).toHaveBeenCalledTimes(1)
  second.unmount()
})
it('does not load a closed panel and pauses when the tab is hidden', async () => {
  const read = vi
    .spyOn(socket, 'read')
    .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 })
  const enabled = ref(false),
    page = ref(1)
  const component = defineComponent({
    setup() {
      useRpcQuery('groups.list', () => ({ page: page.value }), 'groups', enabled)
      return () => h('div')
    },
  })
  const wrapper = mount(component, { global: { plugins: [[VueQueryPlugin, { queryClient }]] } })
  await flushPromises()
  expect(read).not.toHaveBeenCalled()
  enabled.value = true
  await flushPromises()
  expect(read).toHaveBeenCalledTimes(1)
  visible.value = false
  page.value = 2
  await flushPromises()
  expect(read).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
it('generates separate MD3 palettes and surface roles', () => {
  const light = createMaterialTheme(false),
    dark = createMaterialTheme(true)
  expect(light.colors.primary).not.toBe(dark.colors.primary)
  for (const theme of [light, dark])
    for (const role of [
      'on-primary',
      'surface-container',
      'surface-container-low',
      'outline-variant',
      'error-container',
    ])
      expect(theme.colors[role]).toMatch(/^#[0-9a-f]{6}$/i)
})
it('prevents unmount handlers from restoring page state after logout', () => {
  localStorage.setItem('token', 'test')
  pageStates.set('/admin/events', { page: 2, search: 'private' })
  expect(pageStates.size).toBe(1)
  localStorage.removeItem('token')
  pageStates.clear()
  pageStates.set('/admin/events', { page: 2, search: 'private' })
  expect(pageStates.size).toBe(0)
})
it('loads details only for an open dialog and ignores the previous record response', async () => {
  const pending = new Map<number, (value: unknown) => void>()
  const read = vi
    .spyOn(socket, 'read')
    .mockImplementation(
      (method, params) =>
        new Promise((resolve) => pending.set((params as { id: number }).id, resolve)) as ReturnType<
          typeof socket.read
        >,
    )
  let panel!: ReturnType<typeof useResourceDetail>
  const wrapper = mount(
    defineComponent({
      setup() {
        panel = useResourceDetail('audits')
        return () => h('div')
      },
    }),
    { global: { plugins: [[VueQueryPlugin, { queryClient }]] } },
  )
  await flushPromises()
  expect(read).not.toHaveBeenCalled()
  panel.show({ id: 1 })
  await flushPromises()
  panel.show({ id: 2 })
  await flushPromises()
  pending.get(2)!({ id: 2, action: 'current' })
  await flushPromises()
  pending.get(1)!({ id: 1, action: 'previous' })
  await flushPromises()
  expect(panel.query.data.value?.id).toBe(2)
  panel.open.value = false
  wrapper.unmount()
})

it('MD3 text roles meet normal text contrast in both themes', () => {
  function luminance(color: string) {
    const rgb = [1, 3, 5]
      .map((index) => parseInt(color.slice(index, index + 2), 16) / 255)
      .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
  }
  for (const dark of [false, true]) {
    const palette = createMaterialTheme(dark).colors
    for (const role of ['primary', 'secondary', 'tertiary', 'surface', 'error']) {
      const values = [luminance(palette[role]), luminance(palette[`on-${role}`])].sort(
        (a, b) => b - a,
      )
      expect((values[0] + 0.05) / (values[1] + 0.05)).toBeGreaterThanOrEqual(4.5)
    }
  }
})
