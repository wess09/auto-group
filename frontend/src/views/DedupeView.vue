<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">一键去重</h1>
        <p class="page-subtitle">实时拉取群成员，预览确认后再踢出低优先级重复成员。</p>
      </div>
      <div class="toolbar">
        <n-button type="primary" :loading="previewRunning" @click="preview">实时生成预览</n-button>
        <n-button
          type="error"
          :loading="executeRunning"
          :disabled="!canExecute"
          @click="execute"
        >
          确认踢出
        </n-button>
      </div>
    </div>

    <div class="dashboard-grid" style="margin-bottom: 18px">
      <div class="content-band">
        <div class="section-head">
          <div>
            <h3>任务进度</h3>
            <span>{{ phaseText }}</span>
          </div>
          <n-tag :type="statusType">{{ jobStatus }}</n-tag>
        </div>
        <n-progress
          type="line"
          :percentage="progress"
          :indicator-placement="'inside'"
          processing
        />
        <div class="compact-metrics" style="margin-top: 14px">
          <div class="compact-metric">
            <span>已拉取群</span>
            <strong>{{ summary.completed_groups ?? 0 }} / {{ summary.total_groups ?? 0 }}</strong>
          </div>
          <div class="compact-metric">
            <span>重复用户</span>
            <strong>{{ previewData?.duplicate_users ?? 0 }}</strong>
          </div>
          <div class="compact-metric">
            <span>待踢动作</span>
            <strong>{{ previewData?.actions?.length ?? 0 }}</strong>
          </div>
          <div class="compact-metric">
            <span>保护跳过</span>
            <strong>{{ summary.whitelist_skipped ?? 0 }}</strong>
          </div>
        </div>
        <n-alert v-if="summary.current_group_id" type="info" :bordered="false" style="margin-top: 14px">
          正在拉取群 {{ summary.current_group_id }} 的成员列表，单群最多等待 5 分钟。
        </n-alert>
        <n-alert v-if="summary.error" type="error" :bordered="false" style="margin-top: 14px">
          {{ summary.error }}
        </n-alert>
        <n-alert v-if="failedGroups.length" type="warning" :bordered="false" style="margin-top: 14px">
          拉取失败群：{{ failedGroups.join('、') }}。预览不完整，已禁止执行踢人。
        </n-alert>
      </div>

      <div class="content-band">
        <div class="section-head">
          <div>
            <h3>白名单</h3>
            <span>群主和管理员会自动保护，这里添加额外 QQ。</span>
          </div>
        </div>
        <n-input-group class="whitelist-input-group">
          <n-input-number
            v-model:value="whitelistForm.user_id"
            placeholder="QQ"
            :show-button="false"
          />
          <n-input v-model:value="whitelistForm.note" placeholder="备注" />
          <n-button type="primary" @click="addWhitelist">添加</n-button>
        </n-input-group>
        <n-data-table
          style="margin-top: 14px"
          :columns="whitelistColumns"
          :data="whitelist"
          :pagination="{ pageSize: 6 }"
        />
      </div>
    </div>

    <div v-if="skippedMembers.length" class="content-band" style="margin-bottom: 18px">
      <div class="section-head">
        <div>
          <h3>保护跳过</h3>
          <span>这些重复用户不会生成踢人动作。</span>
        </div>
      </div>
      <n-data-table :columns="skippedColumns" :data="skippedMembers" />
    </div>

    <div class="content-band">
      <div class="section-head">
        <div>
          <h3>踢出预览</h3>
          <span>只展示确认后会执行的动作。</span>
        </div>
      </div>
      <n-data-table :columns="columns" :data="previewData?.actions ?? []" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NPopconfirm,
  NSwitch,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const message = useMessage()
const previewData = ref<any>(null)
const whitelist = ref<any[]>([])
const pollingTimer = ref<number | null>(null)
const whitelistForm = reactive({ user_id: null as number | null, note: '' })

const summary = computed(() => previewData.value?.summary ?? {})
const jobStatus = computed(() => previewData.value?.status ?? 'idle')
const failedGroups = computed(() => summary.value.failed_groups ?? [])
const skippedMembers = computed(() => summary.value.skipped_members ?? [])
const previewRunning = computed(() => ['pending', 'running'].includes(jobStatus.value) && summary.value.phase !== 'kicking')
const executeRunning = computed(() => ['pending', 'running'].includes(jobStatus.value) && ['execute_queued', 'kicking'].includes(summary.value.phase))
const canExecute = computed(() =>
  jobStatus.value === 'preview' &&
  (previewData.value?.actions?.length ?? 0) > 0 &&
  !failedGroups.value.length
)
const progress = computed(() => {
  if (summary.value.phase === 'kicking') return summary.value.execute_progress ?? 0
  return summary.value.progress ?? 0
})
const statusType = computed(() => {
  if (jobStatus.value === 'failed') return 'error'
  if (jobStatus.value === 'success' || jobStatus.value === 'preview') return 'success'
  if (jobStatus.value === 'running' || jobStatus.value === 'pending') return 'info'
  return 'default'
})
const phaseText = computed(() => {
  const phase = summary.value.phase
  if (phase === 'queued') return '任务已提交，等待后端开始。'
  if (phase === 'fetching_members') return '正在实时拉取群成员列表。'
  if (phase === 'building_preview') return '正在生成去重预览。'
  if (phase === 'preview_ready') return '预览已完成，请检查后确认踢出。'
  if (phase === 'fetch_failed') return '成员列表拉取失败，不能执行踢人。'
  if (phase === 'execute_queued') return '踢人任务已提交。'
  if (phase === 'kicking') return `正在执行踢人：${summary.value.execute_completed ?? 0} / ${summary.value.execute_total ?? 0}`
  if (phase === 'execute_done') return '踢人执行完成。'
  return '尚未启动任务。'
})

const columns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 150 },
  { title: '昵称', key: 'nickname' },
  { title: '保留群', key: 'keep_group_id', width: 150 },
  { title: '踢出群', key: 'kick_group_id', width: 150 },
  { title: '状态', key: 'status', width: 120 },
  { title: '错误', key: 'error', ellipsis: { tooltip: true } }
]

const skippedColumns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 150 },
  { title: '昵称', key: 'nickname' },
  { title: '原因', key: 'reason', width: 160 },
  { title: '所在群', key: 'groups', render: (row: any) => row.groups?.join('、') ?? '' }
]

const whitelistColumns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 150 },
  { title: '备注', key: 'note' },
  {
    title: '启用',
    key: 'enabled',
    width: 90,
    render: (row: any) =>
      h(NSwitch, { value: row.enabled, 'onUpdate:value': (value: boolean) => toggleWhitelist(row, value) })
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row: any) =>
      h(
        NPopconfirm,
        { onPositiveClick: () => removeWhitelist(row.id) },
        {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          default: () => '确认删除这个白名单？'
        }
      )
  }
]

function clearPolling() {
  if (pollingTimer.value !== null) {
    window.clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

function shouldPoll(data: any) {
  const phase = data?.summary?.phase
  return ['pending', 'running'].includes(data?.status) || ['execute_queued', 'kicking'].includes(phase)
}

async function pollJob(jobId: number) {
  const { data } = await api.get(`/admin/dedupe/jobs/${jobId}`)
  previewData.value = data
  if (!shouldPoll(data)) {
    clearPolling()
  }
}

function startPolling(jobId: number) {
  clearPolling()
  pollingTimer.value = window.setInterval(() => {
    pollJob(jobId).catch(() => {
      clearPolling()
      message.error('任务状态刷新失败')
    })
  }, 1500)
}

async function preview() {
  const { data } = await api.post('/admin/dedupe/preview')
  previewData.value = data
  startPolling(data.job_id)
  message.success('已提交实时预览任务')
}

async function execute() {
  if (!previewData.value?.job_id) return
  const { data } = await api.post('/admin/dedupe/execute', { job_id: previewData.value.job_id })
  previewData.value = { ...previewData.value, status: data.status, summary: data.summary }
  startPolling(data.id)
  message.success('已提交踢人任务')
}

async function loadWhitelist() {
  const { data } = await api.get('/admin/dedupe/whitelist')
  whitelist.value = data
}

async function addWhitelist() {
  if (!whitelistForm.user_id) {
    message.warning('请填写 QQ')
    return
  }
  await api.post('/admin/dedupe/whitelist', {
    user_id: whitelistForm.user_id,
    note: whitelistForm.note
  })
  whitelistForm.user_id = null
  whitelistForm.note = ''
  message.success('已添加白名单')
  loadWhitelist()
}

async function toggleWhitelist(row: any, enabled: boolean) {
  await api.patch(`/admin/dedupe/whitelist/${row.id}`, { enabled })
  row.enabled = enabled
}

async function removeWhitelist(id: number) {
  await api.delete(`/admin/dedupe/whitelist/${id}`)
  message.success('已删除')
  loadWhitelist()
}

onMounted(loadWhitelist)
onBeforeUnmount(clearPolling)
</script>
