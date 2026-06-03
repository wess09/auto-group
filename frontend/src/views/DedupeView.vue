<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">一键去重</h1>
        <p class="page-subtitle">实时拉取群成员，预览确认后再踢出低优先级重复成员。</p>
      </div>
      <div class="toolbar">
        <el-button type="primary" :loading="previewRunning" @click="preview">实时生成预览</el-button>
        <el-button
          type="danger"
          :loading="executeRunning"
          :disabled="!canExecute"
          @click="execute"
        >
          确认踢出
        </el-button>
      </div>
    </div>

    <div class="dashboard-grid" style="margin-bottom: 18px">
      <div class="content-band">
        <div class="section-head">
          <div>
            <h3>任务进度</h3>
            <span>{{ phaseText }}</span>
          </div>
          <el-tag :type="statusType">{{ jobStatus }}</el-tag>
        </div>
        <el-progress
          :percentage="progress"
          :text-inside="true"
          :stroke-width="18"
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
        <el-alert v-if="summary.current_group_id" type="info" :closable="false" style="margin-top: 14px">
          正在拉取群 {{ summary.current_group_id }} 的成员列表，单群最多等待 5 分钟。
        </el-alert>
        <el-alert v-if="summary.error" type="error" :closable="false" style="margin-top: 14px">
          {{ summary.error }}
        </el-alert>
        <el-alert v-if="failedGroups.length" type="warning" :closable="false" style="margin-top: 14px">
          拉取失败群：{{ failedGroups.join('、') }}。预览不完整，已禁止执行踢人。
        </el-alert>
        <el-table
          v-if="failedDetails.length"
          style="margin-top: 14px"
          :data="failedDetails"
          border
        >
          <el-table-column prop="group_id" label="群号" width="140" />
          <el-table-column prop="name" label="群名" width="180" show-overflow-tooltip />
          <el-table-column prop="error" label="失败原因" min-width="220" show-overflow-tooltip />
        </el-table>
      </div>

      <div class="content-band">
        <div class="section-head">
          <div>
            <h3>白名单</h3>
            <span>群主和管理员会自动保护，这里添加额外 QQ。</span>
          </div>
        </div>
        <div class="whitelist-input-group">
          <el-input-number
            v-model="whitelistForm.user_id"
            placeholder="QQ"
            :controls="false"
          />
          <el-input v-model="whitelistForm.note" placeholder="备注" />
          <el-button type="primary" @click="addWhitelist">添加</el-button>
        </div>
        <el-table
          style="margin-top: 14px"
          :data="whitelist"
          border
        >
          <el-table-column prop="user_id" label="QQ" width="150" />
          <el-table-column prop="note" label="备注" />
          <el-table-column label="启用" width="90">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="(value: boolean) => toggleWhitelist(row, value)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-popconfirm title="确认删除这个白名单？" @confirm="removeWhitelist(row.id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div v-if="skippedMembers.length" class="content-band" style="margin-bottom: 18px">
      <div class="section-head">
        <div>
          <h3>保护跳过</h3>
          <span>这些重复用户不会生成踢人动作。</span>
        </div>
      </div>
      <el-table :data="skippedMembers" border>
        <el-table-column prop="user_id" label="QQ" width="150" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column prop="reason" label="原因" width="160" />
        <el-table-column label="所在群" min-width="220">
          <template #default="{ row }">{{ row.groups?.join('、') ?? '' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div class="content-band">
      <div class="section-head">
        <div>
          <h3>踢出预览</h3>
          <span>只展示确认后会执行的动作。</span>
        </div>
      </div>
      <el-table :data="previewData?.actions ?? []" border>
        <el-table-column prop="user_id" label="QQ" width="150" />
        <el-table-column prop="nickname" label="昵称" min-width="160" />
        <el-table-column prop="keep_group_id" label="保留群" width="150" />
        <el-table-column prop="kick_group_id" label="踢出群" width="150" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="error" label="错误" min-width="220" show-overflow-tooltip />
      </el-table>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const previewData = ref<any>(null)
const whitelist = ref<any[]>([])
const pollingTimer = ref<number | null>(null)
const whitelistForm = reactive({ user_id: null as number | null, note: '' })

function normalizeStatus(status: unknown) {
  const value = String(status ?? 'idle')
  return value.includes('.') ? value.split('.').pop() || value : value
}

const summary = computed(() => previewData.value?.summary ?? {})
const jobStatus = computed(() => normalizeStatus(previewData.value?.status))
const failedGroups = computed(() => summary.value.failed_groups ?? [])
const failedDetails = computed(() => summary.value.failed_details ?? [])
const skippedMembers = computed(() => summary.value.skipped_members ?? [])
const previewRunning = computed(() => ['pending', 'running'].includes(jobStatus.value) && summary.value.phase !== 'kicking')
const executeRunning = computed(() => ['pending', 'running'].includes(jobStatus.value) && ['execute_queued', 'kicking'].includes(summary.value.phase))
const canExecute = computed(() =>
  (jobStatus.value === 'preview' || summary.value.phase === 'preview_ready') &&
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
  if (jobStatus.value === 'running' || jobStatus.value === 'pending') return 'primary'
  return 'info'
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

function clearPolling() {
  if (pollingTimer.value !== null) {
    window.clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

function shouldPoll(data: any) {
  const phase = data?.summary?.phase
  return ['pending', 'running'].includes(normalizeStatus(data?.status)) || ['execute_queued', 'kicking'].includes(phase)
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
      ElMessage.error('任务状态刷新失败')
    })
  }, 1500)
}

async function preview() {
  const { data } = await api.post('/admin/dedupe/preview')
  previewData.value = data
  startPolling(data.job_id)
  ElMessage.success('已提交实时预览任务')
}

async function execute() {
  if (!previewData.value?.job_id) return
  const { data } = await api.post('/admin/dedupe/execute', { job_id: previewData.value.job_id })
  previewData.value = { ...previewData.value, status: data.status, summary: data.summary }
  startPolling(data.id)
  ElMessage.success('已提交踢人任务')
}

async function loadWhitelist() {
  const { data } = await api.get('/admin/dedupe/whitelist')
  whitelist.value = data
}

async function addWhitelist() {
  if (!whitelistForm.user_id) {
    ElMessage.warning('请填写 QQ')
    return
  }
  await api.post('/admin/dedupe/whitelist', {
    user_id: whitelistForm.user_id,
    note: whitelistForm.note
  })
  whitelistForm.user_id = null
  whitelistForm.note = ''
  ElMessage.success('已添加白名单')
  loadWhitelist()
}

async function toggleWhitelist(row: any, enabled: boolean) {
  await api.patch(`/admin/dedupe/whitelist/${row.id}`, { enabled })
  row.enabled = enabled
}

async function removeWhitelist(id: number) {
  await api.delete(`/admin/dedupe/whitelist/${id}`)
  ElMessage.success('已删除')
  loadWhitelist()
}

onMounted(loadWhitelist)
onBeforeUnmount(clearPolling)
</script>
