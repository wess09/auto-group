<template>
  <AdminLayout>
    <PageHeader title="事件日志" subtitle="按需查询加群申请、退群事件与后台操作记录。" />
    <v-tabs v-model="tab" color="primary" class="mb-6">
      <v-tab value="joins">加群申请</v-tab>
      <v-tab value="leaves">退群事件</v-tab>
      <v-tab value="audits">操作日志</v-tab>
    </v-tabs>
    <div class="toolbar">
      <GroupPicker v-if="tab !== 'audits'" v-model="groupId" label-text="筛选群（可清空）" />
      <v-text-field v-model="startDate" label="开始日期" type="date" hide-details />
      <v-text-field v-model="endDate" label="结束日期（含当天）" type="date" hide-details />
    </div>
    <ResourceTable :key="tab" :resource="tab" :headers="headers" :filters="filters">
      <template #actions="{ row }">
        <v-btn variant="text" size="small" @click="showDetail(row)">详情</v-btn>
      </template>
    </ResourceTable>
    <v-dialog v-model="dialog" max-width="720" scrollable>
      <v-card title="事件详情">
        <v-card-text>
          <v-progress-linear v-if="loading" indeterminate />
          <QueryError :error="detailQuery.error.value" @retry="detailQuery.refetch()" />
          <pre class="mono text-body-2">{{ detail }}</pre>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AdminLayout>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import AdminLayout from '../components/AdminLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import ResourceTable from '../components/ResourceTable.vue'
import GroupPicker from '../components/GroupPicker.vue'
import { useResourceDetail } from '../api/details'
import QueryError from '../components/QueryError.vue'
import { pageStates } from '../stores/ui'
const route = useRoute(),
  pagePath = route.path,
  state = pageStates.get(pagePath)
const tab = ref<'joins' | 'leaves' | 'audits'>(
    (state?.tab as 'joins' | 'leaves' | 'audits') || 'joins',
  ),
  groupId = ref<number | null>(state?.group || null)
const startDate = ref(state?.startDate || ''),
  endDate = ref(state?.endDate || '')
const { open: dialog, query: detailQuery, show: showDetail } = useResourceDetail(() => tab.value)
const loading = computed(() => detailQuery.isFetching.value)
const detail = computed(() =>
  detailQuery.data.value ? JSON.stringify(detailQuery.data.value, null, 2) : '',
)
const filters = computed(() => ({
  group_id: tab.value === 'audits' ? undefined : groupId.value || undefined,
  start_date: startDate.value || undefined,
  end_date: endDate.value
    ? new Date(new Date(endDate.value).getTime() + 86400000).toISOString().slice(0, 10)
    : undefined,
}))
const headers = computed(() => {
  const fields =
    tab.value === 'joins'
      ? [
          ['QQ', 'user_id'],
          ['群', 'group_id'],
          ['答案', 'answer_text'],
          ['QQ 等级', 'qq_level'],
          ['答错次数', 'wrong_answer_count'],
          ['结果', 'result'],
          ['执行状态', 'apply_status'],
          ['原因', 'reason'],
        ]
      : tab.value === 'leaves'
        ? [
            ['QQ', 'user_id'],
            ['群', 'group_id'],
            ['类型', 'sub_type'],
            ['操作者', 'operator_id'],
          ]
        : [
            ['动作', 'action'],
            ['目标', 'target'],
          ]
  return [...fields, ['时间', 'created_at'], ['操作', 'actions']].map(([title, key]) => ({
    title,
    key,
    sortable: false,
  }))
})
onBeforeUnmount(() =>
  pageStates.set(pagePath, {
    page: 1,
    search: '',
    tab: tab.value,
    group: groupId.value || undefined,
    startDate: startDate.value,
    endDate: endDate.value,
  }),
)
</script>
