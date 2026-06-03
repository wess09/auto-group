<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">群文件</h1>
        <p class="page-subtitle">上传一份文件，选择多个群快速分发。</p>
      </div>
      <n-button @click="loadAll">刷新</n-button>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <n-form-item label="选择目标群">
        <GroupSelector v-model="selectedGroups" :groups="groups" />
      </n-form-item>
      <div class="form-grid">
        <n-form-item label="文件路径">
          <n-input v-model:value="filePath" placeholder="可上传，也可填写 LLBot 可读取的绝对路径" />
        </n-form-item>
        <n-form-item label="群内文件名">
          <n-input v-model:value="fileName" placeholder="留空使用原文件名" />
        </n-form-item>
      </div>
      <n-upload :custom-request="upload" :show-file-list="false">
        <n-button>上传到后端</n-button>
      </n-upload>
      <div class="toolbar" style="margin-top: 12px">
        <n-button type="primary" :disabled="!selectedGroups.length || !filePath" @click="distribute">批量分发</n-button>
        <n-button :disabled="!selectedGroups.length" @click="syncSelected">同步选中群文件</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table :columns="columns" :data="files" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, useMessage, type DataTableColumns, type UploadCustomRequestOptions } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import GroupSelector from '../components/GroupSelector.vue'
import { api, type ManagedGroup } from '../api/client'

const message = useMessage()
const groups = ref<ManagedGroup[]>([])
const files = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const filePath = ref('')
const fileName = ref('')

const columns: DataTableColumns = [
  { title: '群号', key: 'group_id', width: 130 },
  { title: '文件名', key: 'file_name' },
  { title: '文件 ID', key: 'file_id', width: 220, ellipsis: { tooltip: true } },
  { title: '大小', key: 'size', width: 120 },
  { title: '同步时间', key: 'synced_at', width: 210 },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render: (row) => h(NSpace, [
      h(NButton, { size: 'small', onClick: () => getUrl(row) }, { default: () => '链接' }),
      h(NPopconfirm, { onPositiveClick: () => remove(row) }, {
        trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
        default: () => '确认删除群文件？'
      })
    ])
  }
]

async function loadAll() {
  const [groupRes, fileRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/files')])
  groups.value = groupRes.data
  files.value = fileRes.data
}
async function upload(options: UploadCustomRequestOptions) {
  const form = new FormData()
  form.append('file', options.file.file as File)
  const { data } = await api.post('/admin/uploads', form)
  filePath.value = data.file_path
  fileName.value = data.file_name
  message.success('上传完成')
  options.onFinish()
}
async function distribute() {
  const { data } = await api.post('/admin/files/distribute', {
    group_ids: selectedGroups.value,
    file_path: filePath.value,
    name: fileName.value || undefined
  })
  message[data.status === 'success' ? 'success' : 'warning']('分发任务完成')
  loadAll()
}
async function syncSelected() {
  for (const groupId of selectedGroups.value) await api.post(`/admin/files/sync/${groupId}`)
  message.success('同步完成')
  loadAll()
}
async function getUrl(row: any) {
  const { data } = await api.get('/admin/files/url', { params: { group_id: row.group_id, file_id: row.file_id, busid: row.busid } })
  message.info(JSON.stringify(data.data))
}
async function remove(row: any) {
  await api.post('/admin/files/delete', { group_id: row.group_id, file_id: row.file_id, busid: row.busid })
  message.success('已删除')
  loadAll()
}
onMounted(loadAll)
</script>
