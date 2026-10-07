<template>
  <div class="toolbar">
    <v-text-field
      v-model="search"
      class="search"
      label="搜索"
      :prepend-inner-icon="mdiMagnify"
      density="comfortable"
      hide-details
      clearable
      @update:model-value="updateSearch"
    />
    <slot name="toolbar" />
    <v-spacer />
    <v-btn
      variant="text"
      :prepend-icon="mdiRefresh"
      :loading="query.isFetching.value"
      @click="query.refetch()"
    >
      刷新
    </v-btn>
  </div>
  <QueryError :error="query.error.value" @retry="query.refetch()" />
  <v-card class="surface-card">
    <v-data-table-server
      class="resource-table"
      :mobile="false"
      :headers="headers"
      :items="rows"
      :items-length="total"
      :items-per-page="25"
      :items-per-page-options="[25]"
      :page="page"
      :loading="query.isFetching.value"
      @update:page="setPage"
    >
      <template #item="{ item, index }">
        <tr :data-index="index">
          <td v-for="column in headers" :key="column.key">
            <slot
              v-if="column.key === 'actions'"
              name="actions"
              :row="item"
              :index="index"
              :position="(page - 1) * 25 + index + 1"
            />
            <slot v-else-if="column.key === 'drag'" name="drag" :row="item" />
            <v-chip
              v-else-if="typeof item[column.key] === 'boolean'"
              size="small"
              :color="item[column.key] ? 'primary' : undefined"
            >
              {{ item[column.key] ? '启用' : '停用' }}
            </v-chip>
            <span v-else>{{ format(item[column.key], column.key) }}</span>
          </td>
        </tr>
      </template>
      <template #no-data><div class="py-12 muted">暂无数据</div></template>
    </v-data-table-server>
  </v-card>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { mdiMagnify, mdiRefresh } from '@mdi/js'
import { useRpcQuery } from '../api/queries'
import type { DataRow, PageInput, Resource } from '../api/types'
import { pageStates } from '../stores/ui'
import QueryError from './QueryError.vue'
const props = withDefaults(
  defineProps<{
    resource: Resource
    headers: { title: string; key: string; sortable?: boolean; width?: number | string }[]
    filters?: PageInput
    enabled?: boolean
    topic?: string
  }>(),
  { filters: () => ({}), enabled: true, topic: '' },
)
const route = useRoute()
const pagePath = route.path
const stateKey = () => `${pagePath}:${props.resource}`
const page = ref(pageStates.get(stateKey())?.page || 1),
  search = ref(pageStates.get(stateKey())?.search || '')
const debounced = ref(search.value)
let timer: ReturnType<typeof setTimeout> | undefined
function save() {
  pageStates.set(stateKey(), { page: page.value, search: search.value || '' })
}
function updateSearch() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    debounced.value = search.value || ''
    page.value = 1
    save()
  }, 300)
}
function setPage(value: number) {
  page.value = value
  save()
}
watch(
  () => props.resource,
  () => {
    const saved = pageStates.get(stateKey())
    page.value = saved?.page || 1
    search.value = saved?.search || ''
    debounced.value = search.value
  },
)
watch(
  () => JSON.stringify(props.filters),
  () => {
    page.value = 1
  },
)
const query = useRpcQuery(
  () => `${props.resource}.list` as const,
  () => ({ ...props.filters, page: page.value, q: debounced.value }),
  () =>
    props.topic ||
    (props.filters.group_id ? `${props.resource}:${props.filters.group_id}` : props.resource),
  () => props.enabled,
)
const rows = computed<DataRow[]>(() => query.data.value?.items || [])
// Keep the last known count while a new page loads so the table does not reset to page 1.
const total = ref(0)
watch(
  query.data,
  (data) => {
    if (data) total.value = data.total
  },
  { immediate: true },
)
function format(value: unknown, key: string) {
  if (value === undefined || value === null || value === '') return '—'
  if (key.endsWith('_at') && typeof value === 'string')
    return new Date(
      value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z',
    ).toLocaleString('zh-CN')
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
onBeforeUnmount(() => {
  clearTimeout(timer)
  save()
})
defineExpose({
  refetch: () => query.refetch(),
  rows,
  page,
  total,
  filtered: computed(() => !!debounced.value),
})
</script>
