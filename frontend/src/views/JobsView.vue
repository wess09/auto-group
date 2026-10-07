<template>
  <AdminLayout>
    <PageHeader
      title="后台任务"
      subtitle="离开页面后任务继续执行。中断的任务需要核实结果后重新提交。"
    />
    <ResourceTable resource="jobs" :headers="headers">
      <template #actions="{ row }">
        <v-btn variant="text" size="small" @click="selected = row.id">查看进度与明细</v-btn>
      </template>
    </ResourceTable>
    <div v-if="selected" class="mt-6">
      <JobPanel :job-id="selected" />
      <v-tabs v-if="job?.dedupe_job_id" v-model="detailTab" color="primary" class="mb-5">
        <v-tab value="results">逐群结果</v-tab>
        <v-tab value="actions">去重操作明细</v-tab>
      </v-tabs>
      <h2 class="text-title-medium mb-4">逐项结果</h2>
      <ResourceTable
        v-if="detailTab === 'results'"
        :key="selected"
        resource="job-items"
        :headers="itemHeaders"
        :filters="{ job_id: selected }"
        :topic="`jobs:${selected}`"
      >
        <template #actions="{ row }">
          <v-btn variant="text" size="small" @click="show(row)">详情</v-btn>
        </template>
      </ResourceTable>
      <ResourceTable
        v-else-if="job?.dedupe_job_id"
        :key="job.dedupe_job_id"
        resource="actions"
        :headers="actionHeaders"
        :filters="{ job_id: job.dedupe_job_id }"
        :topic="`jobs:${selected}`"
      />
    </div>
    <v-dialog v-model="dialog" max-width="720" scrollable>
      <v-card title="任务项详情">
        <v-card-text>
          <v-progress-linear v-if="detailQuery.isFetching.value" indeterminate />
          <QueryError :error="detailQuery.error.value" @retry="detailQuery.refetch()" />
          <pre class="mono">{{ detail }}</pre>
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useResourceDetail } from '../api/details'
import QueryError from '../components/QueryError.vue'
import { useRpcQuery } from '../api/queries'
import { pageStates } from '../stores/ui'
import AdminLayout from '../components/AdminLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import ResourceTable from '../components/ResourceTable.vue'
import JobPanel from '../components/JobPanel.vue'
const route = useRoute()
const pagePath = route.path
const selected = ref<number | null>(pageStates.get(pagePath)?.jobId || null),
  detailTab = ref('results')
const query = useRpcQuery(
  'jobs.get',
  () => ({ id: selected.value || 0 }),
  () => `jobs:${selected.value}`,
  () => !!selected.value,
)
const job = computed(() => query.data.value)
watch(selected, () => {
  detailTab.value = 'results'
})
const actionHeaders = [
  ['QQ', 'user_id'],
  ['昵称', 'nickname'],
  ['保留群', 'keep_group_id'],
  ['踢出群', 'kick_group_id'],
  ['状态', 'status'],
  ['错误', 'error'],
].map(([title, key]) => ({ title, key, sortable: false }))
const headers = [
  ['编号', 'id'],
  ['任务类型', 'kind'],
  ['状态', 'status'],
  ['提交时间', 'created_at'],
  ['操作', 'actions'],
].map(([title, key]) => ({ title, key, sortable: false }))
const itemHeaders = [
  ['群', 'group_id'],
  ['状态', 'status'],
  ['错误', 'error'],
  ['操作', 'actions'],
].map(([title, key]) => ({ title, key, sortable: false }))
const { open: dialog, query: detailQuery, show } = useResourceDetail('job-items')
const detail = computed(() =>
  detailQuery.data.value ? JSON.stringify(detailQuery.data.value, null, 2) : '',
)
onBeforeUnmount(() =>
  pageStates.set(pagePath, { page: 1, search: '', jobId: selected.value || undefined }),
)
</script>
