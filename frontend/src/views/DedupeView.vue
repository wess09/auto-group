<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">一键去重</h1>
        <p class="page-subtitle">先预览重复成员，确认后保留最高优先级群。</p>
      </div>
      <div class="toolbar">
        <n-button type="primary" @click="preview">生成预览</n-button>
        <n-button type="error" :disabled="!previewData?.actions?.length" @click="execute">确认踢出</n-button>
      </div>
    </div>
    <n-alert v-if="previewData" type="info" :bordered="false" style="margin-bottom: 16px">
      发现 {{ previewData.duplicate_users }} 个重复用户，将执行 {{ previewData.actions.length }} 个踢出动作。
    </n-alert>
    <div class="content-band">
      <n-data-table :columns="columns" :data="previewData?.actions ?? []" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMessage, type DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const message = useMessage()
const previewData = ref<any>(null)
const columns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 150 },
  { title: '昵称', key: 'nickname' },
  { title: '保留群', key: 'keep_group_id', width: 150 },
  { title: '踢出群', key: 'kick_group_id', width: 150 }
]

async function preview() {
  const { data } = await api.post('/admin/dedupe/preview')
  previewData.value = data
  message.success('预览已生成')
}
async function execute() {
  const { data } = await api.post('/admin/dedupe/execute', { job_id: previewData.value.job_id })
  message[data.status === 'success' ? 'success' : 'warning'](`执行完成：成功 ${data.summary.success ?? 0}，失败 ${data.summary.failed ?? 0}`)
}
</script>
