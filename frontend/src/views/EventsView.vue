<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">事件日志</h1>
        <p class="page-subtitle">查看加群申请、退群监听和后台操作日志。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <h3>加群申请</h3>
      <el-table :data="joins" border>
        <el-table-column prop="user_id" label="QQ" width="130" />
        <el-table-column prop="group_id" label="群号" width="130" />
        <el-table-column prop="answer_text" label="答案" min-width="180" show-overflow-tooltip />
        <el-table-column prop="result" label="结果" width="120" />
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="210" />
      </el-table>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <h3>退群事件</h3>
      <el-table :data="leaves" border>
        <el-table-column prop="user_id" label="QQ" width="130" />
        <el-table-column prop="group_id" label="群号" width="130" />
        <el-table-column prop="sub_type" label="类型" width="120" />
        <el-table-column prop="operator_id" label="操作者" width="130" />
        <el-table-column prop="created_at" label="时间" />
      </el-table>
    </div>
    <div class="content-band">
      <h3>操作日志</h3>
      <el-table :data="audits" border>
        <el-table-column prop="action" label="动作" width="170" />
        <el-table-column prop="target" label="目标" width="180" />
        <el-table-column prop="created_at" label="时间" width="210" />
        <el-table-column label="详情" min-width="260">
          <template #default="{ row }">
            <code class="json-cell">{{ JSON.stringify(row.detail) }}</code>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const joins = ref<any[]>([])
const leaves = ref<any[]>([])
const audits = ref<any[]>([])

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
