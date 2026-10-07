<template>
  <v-autocomplete
    :model-value="modelValue"
    :items="options"
    :item-title="label"
    item-value="group_id"
    :label="labelText"
    :loading="query.isFetching.value"
    :error-messages="query.error.value?.message"
    :no-filter="true"
    clearable
    :return-object="false"
    @update:model-value="select"
    @update:search="updateSearch"
    v-model:menu="menu"
  >
    <template #append-item>
      <div v-if="query.data.value && query.data.value.total > 25" class="px-3 py-2">
        <v-pagination
          v-model="page"
          :length="Math.ceil(query.data.value.total / 25)"
          :total-visible="3"
          density="compact"
        />
      </div>
    </template>
  </v-autocomplete>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRpcQuery } from '../api/queries'
import type { GroupOption } from '../api/types'
const props = withDefaults(
  defineProps<{ modelValue: number | null | undefined; labelText?: string }>(),
  { labelText: '选择群' },
)
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const menu = ref(false),
  page = ref(1),
  q = ref('')
const selected = ref<GroupOption | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
function updateSearch(value: string) {
  clearTimeout(timer)
  if (selected.value && value === label(selected.value)) return
  timer = setTimeout(() => {
    q.value = value || ''
    page.value = 1
  }, 300)
}
const query = useRpcQuery(
  'groups.options',
  () => ({ page: page.value, q: q.value }),
  'groups',
  () => menu.value,
)
const lookup = useRpcQuery(
  'groups.options',
  () => ({ group_id: props.modelValue ?? undefined }),
  'groups',
  () => !!props.modelValue && !selected.value,
)
watch(
  () => lookup.data.value,
  (result) => {
    if (result?.items[0]) selected.value = result.items[0]
  },
)
watch(
  () => props.modelValue,
  (value) => {
    if (value !== selected.value?.group_id)
      selected.value = query.data.value?.items.find((item) => item.group_id === value) || null
  },
)
const options = computed(() => {
  const rows = query.data.value?.items || []
  return selected.value && !rows.some((row) => row.group_id === selected.value?.group_id)
    ? [selected.value, ...rows]
    : rows
})
function select(value: number | null) {
  clearTimeout(timer)
  selected.value = query.data.value?.items.find((item) => item.group_id === value) || null
  menu.value = false
  emit('update:modelValue', value)
}
function label(group: GroupOption) {
  return `${group.name || '未命名群'} · ${group.group_id}`
}
onBeforeUnmount(() => clearTimeout(timer))
</script>
