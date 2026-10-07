<template>
  <v-card v-if="jobId" class="surface-card pa-5 mb-6">
    <div class="d-flex align-center justify-space-between ga-2 mb-3">
      <h2 class="text-title-medium">任务 #{{ jobId }}</h2>
      <v-chip size="small" :color="statusColor">{{ statusText }}</v-chip>
    </div>
    <QueryError :error="query.error.value" @retry="query.refetch()" />
    <div v-if="job" class="text-body-2 mb-3">
      {{ job.summary.phase }} · 已完成 {{ job.summary.completed || 0 }} /
      {{ job.summary.total || job.summary.actions || 0 }}
      <span v-if="job.summary.failed">· 失败 {{ job.summary.failed }}</span>
    </div>
    <v-progress-linear
      v-if="running"
      :model-value="progress"
      :indeterminate="!Number(job?.summary.total || job?.summary.actions)"
      rounded
    />
    <v-alert v-if="job?.summary.error" type="warning" variant="tonal" class="mt-3">
      {{ job.summary.error }}
    </v-alert>
    <slot :job="job" />
    <v-btn variant="text" class="mt-2" :to="adminPath('jobs')">查看全部任务与明细</v-btn>
  </v-card>
</template>
<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRpcQuery } from '../api/queries'
import { adminPath } from '../adminRoute'
import QueryError from './QueryError.vue'
const props = defineProps<{ jobId: number | null }>()
const emit = defineEmits<{ completed: [] }>()
const query = useRpcQuery(
  'jobs.get',
  () => ({ id: props.jobId || 0 }),
  () => `jobs:${props.jobId}`,
  () => !!props.jobId,
)
const job = computed(() => query.data.value)
const running = computed(() => ['pending', 'running'].includes(job.value?.status || ''))
const statusText = computed(
  () =>
    ({
      pending: '等待执行',
      running: '执行中',
      success: '已完成',
      preview: '预览完成',
      failed: '失败',
      interrupted: '已中断',
    })[job.value?.status || ''] || '加载中',
)
const statusColor = computed(() =>
  ['failed', 'interrupted'].includes(job.value?.status || '') ? 'error' : 'primary',
)
const progress = computed(
  () =>
    (Number(job.value?.summary.completed || 0) /
      Math.max(1, Number(job.value?.summary.total || job.value?.summary.actions))) *
    100,
)
watch(
  () => job.value?.status,
  (next, previous) => {
    if (
      previous &&
      ['pending', 'running'].includes(previous) &&
      next &&
      !['pending', 'running'].includes(next)
    )
      emit('completed')
  },
)
defineExpose({ job })
</script>
