<template>
  <v-card variant="outlined" rounded="lg" class="pa-4">
    <div class="toolbar">
      <v-text-field
        v-model="search"
        label="搜索目标群"
        density="compact"
        hide-details
        :prepend-inner-icon="mdiMagnify"
        @update:model-value="updateSearch"
      />
      <v-btn variant="text" @click="clear">清空</v-btn>
    </div>
    <QueryError :error="query.error.value" @retry="query.refetch()" />
    <v-checkbox
      :model-value="modelValue.mode === 'all_matching'"
      label="全选符合筛选条件的群"
      hide-details
      @update:model-value="selectAll"
    />
    <div class="muted text-body-2 mb-3">
      {{
        modelValue.mode === 'all_matching'
          ? `已选全部匹配群，排除 ${modelValue.excluded_ids.length} 个`
          : `已选 ${modelValue.ids.length} 个群`
      }}
    </div>
    <v-progress-linear v-if="query.isFetching.value" indeterminate />
    <v-list bg-color="transparent" density="compact" max-height="280" class="overflow-y-auto">
      <v-list-item
        v-for="group in query.data.value?.items || []"
        :key="group.group_id"
        :title="group.name || '未命名群'"
        :subtitle="String(group.group_id)"
        @click="toggle(group.group_id)"
      >
        <template #prepend>
          <v-checkbox-btn :model-value="checked(group.group_id)" tabindex="-1" readonly />
        </template>
      </v-list-item>
    </v-list>
    <v-pagination
      v-if="query.data.value && query.data.value.total > 25"
      v-model="page"
      :length="Math.ceil(query.data.value.total / 25)"
      :total-visible="4"
      density="compact"
    />
  </v-card>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { mdiMagnify } from '@mdi/js'
import { useRpcQuery } from '../api/queries'
import { emptySelection, type Selection } from '../api/types'
import QueryError from './QueryError.vue'
const props = defineProps<{ modelValue: Selection }>()
const emit = defineEmits<{ 'update:modelValue': [value: Selection] }>()
const search = ref(''),
  q = ref(''),
  page = ref(1)
let timer: ReturnType<typeof setTimeout> | undefined
const query = useRpcQuery('groups.options', () => ({ page: page.value, q: q.value }), 'groups')
function updateSearch() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    q.value = search.value || ''
    page.value = 1
    if (props.modelValue.mode === 'all_matching')
      emit('update:modelValue', { ...props.modelValue, q: q.value, excluded_ids: [] })
  }, 300)
}
function clear() {
  emit('update:modelValue', emptySelection())
}
function selectAll(checked: boolean | null) {
  emit(
    'update:modelValue',
    checked ? { ...emptySelection(), mode: 'all_matching', q: q.value } : emptySelection(),
  )
}
function checked(id: number) {
  return props.modelValue.mode === 'all_matching'
    ? !props.modelValue.excluded_ids.includes(id)
    : props.modelValue.ids.includes(id)
}
function toggle(id: number) {
  const key = props.modelValue.mode === 'all_matching' ? 'excluded_ids' : 'ids'
  const ids = props.modelValue[key]
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id],
  })
}
onBeforeUnmount(() => clearTimeout(timer))
</script>
