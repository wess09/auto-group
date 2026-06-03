<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">精华管理</h1>
        <p class="page-subtitle">把指定内容发送到单群或多群，并自动设为精华。</p>
      </div>
      <n-button @click="loadAll">刷新</n-button>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <n-form-item label="目标群">
        <GroupSelector v-model="selectedGroups" :groups="groups" />
      </n-form-item>
      <n-form-item label="精华内容">
        <n-input v-model:value="content" type="textarea" />
      </n-form-item>
      <div class="toolbar">
        <n-button type="primary" :disabled="!selectedGroups.length || !content" @click="create">发送并设精</n-button>
        <n-button :disabled="!selectedGroups.length" @click="syncSelected">同步选中群精华</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table :columns="columns" :data="essence" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { NButton, NPopconfirm, useMessage, type DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import GroupSelector from '../components/GroupSelector.vue'
import { api, type ManagedGroup } from '../api/client'

const message = useMessage()
const groups = ref<ManagedGroup[]>([])
const essence = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const content = ref('')

const columns: DataTableColumns = [
  { title: '群号', key: 'group_id', width: 130 },
  { title: '消息 ID', key: 'message_id', width: 130 },
  { title: '发送者', key: 'sender_id', width: 130 },
  { title: '内容', key: 'content', ellipsis: { tooltip: true } },
  { title: '同步时间', key: 'synced_at', width: 210 },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row) => h(NPopconfirm, { onPositiveClick: () => remove(row) }, {
      trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '移出精华' }),
      default: () => '确认移出精华？'
    })
  }
]

async function loadAll() {
  const [groupRes, essenceRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/essence')])
  groups.value = groupRes.data
  essence.value = essenceRes.data
}
async function create() {
  const { data } = await api.post('/admin/essence/create', { group_ids: selectedGroups.value, content: content.value })
  message[data.ok ? 'success' : 'warning']('任务完成')
  content.value = ''
  loadAll()
}
async function syncSelected() {
  for (const groupId of selectedGroups.value) await api.post(`/admin/essence/sync/${groupId}`)
  message.success('同步完成')
  loadAll()
}
async function remove(row: any) {
  await api.post('/admin/essence/delete', { group_id: row.group_id, message_ids: [row.message_id] })
  message.success('已移出')
  loadAll()
}
onMounted(loadAll)
</script>
