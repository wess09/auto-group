<template>
  <ResourceEditor v-if="tab === 'whitelist'" resource="whitelist">
    <template #header><v-btn variant="tonal" @click="tab = 'preview'">返回去重</v-btn></template>
  </ResourceEditor>
  <AdminLayout v-else>
    <PageHeader
      title="一键去重"
      subtitle="实时拉取群成员，保留优先级最高的群。群主、管理员和白名单成员受到保护。"
    >
      <v-btn variant="tonal" @click="tab = 'whitelist'">管理白名单</v-btn>
      <v-btn :loading="submitting" :disabled="running" @click="preview">生成预览</v-btn>
    </PageHeader>
    <v-card v-if="!jobId" class="surface-card pa-8 mb-6">
      <h2 class="text-title-large mb-3">先预览，再执行</h2>
      <p class="muted">预览只计算重复成员与保留群。成员同步失败时禁止执行踢人。</p>
    </v-card>
    <JobPanel :job-id="jobId">
      <template #default="{ job }">
        <div v-if="job" class="d-flex ga-5 flex-wrap mt-4">
          <span>重复成员 {{ job.summary.duplicate_users || 0 }}</span>
          <span>待执行动作 {{ job.summary.actions || 0 }}</span>
          <span>保护成员 {{ job.summary.whitelist_skipped || 0 }}</span>
          <v-btn
            v-if="job.kind === 'dedupe.preview' && job.status === 'preview'"
            color="error"
            :disabled="!Number(job.summary.actions)"
            @click="confirm = true"
          >
            确认执行踢人
          </v-btn>
        </div>
      </template>
    </JobPanel>
    <v-tabs v-if="jobId" v-model="detailTab" color="primary" class="mb-5">
      <v-tab value="actions">操作明细</v-tab>
      <v-tab value="results">同步与保护明细</v-tab>
    </v-tabs>
    <ResourceTable
      v-if="detailTab === 'actions' && job?.dedupe_job_id"
      :key="job.dedupe_job_id"
      resource="actions"
      :headers="actionHeaders"
      :filters="{ job_id: job.dedupe_job_id }"
      :topic="`jobs:${jobId}`"
    />
    <ResourceTable
      v-else-if="detailTab === 'results' && jobId"
      :key="jobId"
      resource="job-items"
      :headers="resultHeaders"
      :filters="{ job_id: jobId }"
      :topic="`jobs:${jobId}`"
    >
      <template #actions="{ row }">
        <v-btn variant="text" size="small" @click="show(row)">详情</v-btn>
      </template>
    </ResourceTable>
    <v-dialog v-model="confirm" max-width="500">
      <v-card
        title="确认执行去重"
        text="将按预览踢出低优先级群中的重复成员。此操作不能撤销，执行时仍会检查白名单与管理员保护。"
      >
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirm = false">取消</v-btn>
          <v-btn color="error" :loading="submitting" @click="execute">执行踢人</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="detailOpen" max-width="680" scrollable>
      <v-card title="保护或同步详情">
        <v-card-text>
          <v-progress-linear v-if="detailQuery.isFetching.value" indeterminate />
          <QueryError :error="detailQuery.error.value" @retry="detailQuery.refetch()" />
          <pre class="mono">{{ detail }}</pre>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="detailOpen = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AdminLayout>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useResourceDetail } from '../api/details'
import QueryError from '../components/QueryError.vue'
import { submitJob } from '../api/jobs'
import { useRpcQuery } from '../api/queries'
import { pageStates, report } from '../stores/ui'
import AdminLayout from '../components/AdminLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import ResourceEditor from '../components/ResourceEditor.vue'
import ResourceTable from '../components/ResourceTable.vue'
import JobPanel from '../components/JobPanel.vue'
const route = useRoute(),
  pagePath = route.path,
  tab = ref('preview'),
  detailTab = ref('actions'),
  jobId = ref<number | null>(pageStates.get(pagePath)?.jobId || null),
  submitting = ref(false),
  confirm = ref(false)

const query = useRpcQuery(
  'jobs.get',
  () => ({ id: jobId.value || 0 }),
  () => `jobs:${jobId.value}`,
  () => !!jobId.value && tab.value === 'preview',
)
const job = computed(() => query.data.value),
  running = computed(() => ['pending', 'running'].includes(job.value?.status || ''))
const actionHeaders = [
  ['QQ', 'user_id'],
  ['昵称', 'nickname'],
  ['保留群', 'keep_group_id'],
  ['踢出群', 'kick_group_id'],
  ['状态', 'status'],
  ['错误', 'error'],
].map(([title, key]) => ({ title, key, sortable: false }))
const resultHeaders = [
  ['群', 'group_id'],
  ['状态', 'status'],
  ['错误', 'error'],
  ['操作', 'actions'],
].map(([title, key]) => ({ title, key, sortable: false }))
async function preview() {
  submitting.value = true
  try {
    jobId.value = (await submitJob('dedupe.preview', {})).id
  } catch (error) {
    report(error)
  } finally {
    submitting.value = false
  }
}
async function execute() {
  if (!jobId.value) return
  submitting.value = true
  try {
    jobId.value = (await submitJob('dedupe.execute', { job_id: jobId.value })).id
    confirm.value = false
  } catch (error) {
    report(error)
  } finally {
    submitting.value = false
  }
}
const { open: detailOpen, query: detailQuery, show } = useResourceDetail('job-items')
const detail = computed(() =>
  detailQuery.data.value ? JSON.stringify(detailQuery.data.value, null, 2) : '',
)
onBeforeUnmount(() =>
  pageStates.set(pagePath, { page: 1, search: '', jobId: jobId.value || undefined }),
)
</script>
