<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">仪表盘</h1>
        <p class="page-subtitle">群审核、运营内容和最近后台动作的概览。</p>
      </div>
      <n-button @click="load">刷新</n-button>
    </div>
    <div class="metric-grid">
      <div v-for="item in metrics" :key="item.label" class="metric">
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-value">{{ item.value }}</div>
      </div>
    </div>
    <div class="content-band" style="margin-top: 18px">
      <h3>最近操作</h3>
      <n-data-table :columns="logColumns" :data="dashboard?.recent_audit_logs ?? []" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const dashboard = ref<any>(null)

const metrics = computed(() => [
  { label: '受管群', value: dashboard.value?.groups ?? 0 },
  { label: '启用群', value: dashboard.value?.enabled_groups ?? 0 },
  { label: '入群申请', value: dashboard.value?.join_requests ?? 0 },
  { label: '退群事件', value: dashboard.value?.leave_events ?? 0 },
  { label: '公告', value: dashboard.value?.announcements ?? 0 },
  { label: '群文件', value: dashboard.value?.files ?? 0 },
  { label: '精华消息', value: dashboard.value?.essence_messages ?? 0 }
])

const logColumns: DataTableColumns = [
  { title: '动作', key: 'action', width: 160 },
  { title: '目标', key: 'target', width: 180 },
  { title: '时间', key: 'created_at' },
  { title: '详情', key: 'detail', render: (row) => h('code', JSON.stringify(row.detail)) }
]

async function load() {
  const { data } = await api.get('/admin/dashboard')
  dashboard.value = data
}

onMounted(load)
</script>
