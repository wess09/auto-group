<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">公告管理</h1>
        <p class="page-subtitle">同步各群公告，批量发送或删除指定公告。</p>
      </div>
      <div class="toolbar"><n-button @click="loadAll">刷新</n-button></div>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <div class="form-grid">
        <n-form-item label="目标群">
          <n-checkbox-group v-model:value="selectedGroups">
            <n-space>
              <n-checkbox v-for="group in groups" :key="group.group_id" :value="group.group_id">
                {{ group.name || group.group_id }}
              </n-checkbox>
            </n-space>
          </n-checkbox-group>
        </n-form-item>
      </div>
      <n-form-item label="公告内容">
        <n-input v-model:value="noticeContent" type="textarea" />
      </n-form-item>
      <div class="toolbar">
        <n-button type="primary" :disabled="!selectedGroups.length || !noticeContent" @click="send">批量发送</n-button>
        <n-button :disabled="!selectedGroups.length" @click="syncSelected">同步选中群</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table :columns="columns" :data="notices" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, useMessage, type DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type ManagedGroup } from '../api/client'

const message = useMessage()
const groups = ref<ManagedGroup[]>([])
const notices = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const noticeContent = ref('')

const columns: DataTableColumns = [
  { title: '群号', key: 'group_id', width: 130 },
  { title: '公告 ID', key: 'notice_id', width: 190 },
  { title: '标题', key: 'title', width: 180 },
  { title: '内容', key: 'content', ellipsis: { tooltip: true } },
  { title: '同步时间', key: 'synced_at', width: 210 },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(NPopconfirm, { onPositiveClick: () => remove(row) }, {
      trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
      default: () => '确认删除这条公告？'
    })
  }
]

async function loadAll() {
  const [groupRes, noticeRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/notices')])
  groups.value = groupRes.data
  notices.value = noticeRes.data
}
async function send() {
  const { data } = await api.post('/admin/notices/send', { group_ids: selectedGroups.value, content: noticeContent.value })
  message[data.ok ? 'success' : 'warning'](data.ok ? '发送完成' : '部分群发送失败')
  noticeContent.value = ''
  loadAll()
}
async function syncSelected() {
  for (const groupId of selectedGroups.value) {
    await api.post(`/admin/notices/sync/${groupId}`)
  }
  message.success('同步完成')
  loadAll()
}
async function remove(row: any) {
  const { data } = await api.post('/admin/notices/delete', { group_id: row.group_id, notice_ids: [row.notice_id] })
  message[data.ok ? 'success' : 'warning']('删除完成')
  loadAll()
}
onMounted(loadAll)
</script>
