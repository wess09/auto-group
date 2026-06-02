<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">事件日志</h1>
        <p class="page-subtitle">查看加群申请、退群监听和后台操作日志。</p>
      </div>
      <n-button @click="load">刷新</n-button>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <h3>加群申请</h3>
      <n-data-table :columns="joinColumns" :data="joins" />
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <h3>退群事件</h3>
      <n-data-table :columns="leaveColumns" :data="leaves" />
    </div>
    <div class="content-band">
      <h3>操作日志</h3>
      <n-data-table :columns="auditColumns" :data="audits" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const joins = ref<any[]>([])
const leaves = ref<any[]>([])
const audits = ref<any[]>([])

const joinColumns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 130 },
  { title: '群号', key: 'group_id', width: 130 },
  { title: '答案', key: 'answer_text' },
  { title: '结果', key: 'result', width: 120 },
  { title: '原因', key: 'reason', ellipsis: { tooltip: true } },
  { title: '时间', key: 'created_at', width: 210 }
]
const leaveColumns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 130 },
  { title: '群号', key: 'group_id', width: 130 },
  { title: '类型', key: 'sub_type', width: 120 },
  { title: '操作者', key: 'operator_id', width: 130 },
  { title: '时间', key: 'created_at' }
]
const auditColumns: DataTableColumns = [
  { title: '动作', key: 'action', width: 170 },
  { title: '目标', key: 'target', width: 180 },
  { title: '时间', key: 'created_at', width: 210 },
  { title: '详情', key: 'detail', render: (row) => h('code', JSON.stringify(row.detail)) }
]

async function load() {
  const [joinRes, leaveRes, auditRes] = await Promise.all([
    api.get('/admin/join-requests'),
    api.get('/admin/leave-events'),
    api.get('/admin/audit-logs')
  ])
  joins.value = joinRes.data
  leaves.value = leaveRes.data
  audits.value = auditRes.data
}

onMounted(load)
</script>
