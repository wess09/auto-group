<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">群文件</h1>
        <p class="page-subtitle">上传一份文件，选择多个群快速分发。</p>
      </div>
      <el-button @click="loadAll">刷新</el-button>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <el-form-item label="选择目标群">
        <GroupSelector v-model="selectedGroups" :groups="groups" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="文件路径">
          <el-input v-model="filePath" placeholder="可上传，也可填写 LLBot 可读取的绝对路径" />
        </el-form-item>
        <el-form-item label="群内文件名">
          <el-input v-model="fileName" placeholder="留空使用原文件名" />
        </el-form-item>
      </div>
      <el-upload :http-request="upload" :show-file-list="false">
        <el-button>上传到后端</el-button>
      </el-upload>
      <div class="toolbar" style="margin-top: 12px">
        <el-button type="primary" :disabled="!selectedGroups.length || !filePath" @click="distribute">批量分发</el-button>
        <el-button :disabled="!selectedGroups.length" @click="syncSelected">同步选中群文件</el-button>
      </div>
    </div>
    <div class="content-band">
      <el-table :data="files" border>
        <el-table-column prop="group_id" label="群号" width="130" />
        <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_id" label="文件 ID" width="220" show-overflow-tooltip />
        <el-table-column prop="size" label="大小" width="120" />
        <el-table-column prop="synced_at" label="同步时间" width="210" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="getUrl(row)">链接</el-button>
              <el-popconfirm title="确认删除群文件？" @confirm="remove(row)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import AdminLayout from '../components/AdminLayout.vue'
import GroupSelector from '../components/GroupSelector.vue'
import { api, type ManagedGroup } from '../api/client'

const groups = ref<ManagedGroup[]>([])
const files = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const filePath = ref('')
const fileName = ref('')

async function loadAll() {
  const [groupRes, fileRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/files')])
  groups.value = groupRes.data
  files.value = fileRes.data
}
async function upload(options: UploadRequestOptions) {
  const form = new FormData()
  form.append('file', options.file)
  try {
    const { data } = await api.post('/admin/uploads', form)
    filePath.value = data.file_path
    fileName.value = data.file_name
    ElMessage.success('上传完成')
    options.onSuccess(data)
  } catch (error) {
    options.onError(error as Parameters<typeof options.onError>[0])
  }
}
async function distribute() {
  const { data } = await api.post('/admin/files/distribute', {
    group_ids: selectedGroups.value,
    file_path: filePath.value,
    name: fileName.value || undefined
  })
  ElMessage[data.status === 'success' ? 'success' : 'warning']('分发任务完成')
  loadAll()
}
async function syncSelected() {
  for (const groupId of selectedGroups.value) await api.post(`/admin/files/sync/${groupId}`)
  ElMessage.success('同步完成')
  loadAll()
}
async function getUrl(row: any) {
  const { data } = await api.get('/admin/files/url', { params: { group_id: row.group_id, file_id: row.file_id, busid: row.busid } })
  ElMessage.info(JSON.stringify(data.data))
}
async function remove(row: any) {
  await api.post('/admin/files/delete', { group_id: row.group_id, file_id: row.file_id, busid: row.busid })
  ElMessage.success('已删除')
  loadAll()
}
onMounted(loadAll)
</script>
