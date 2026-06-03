<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">公告管理</h1>
        <p class="page-subtitle">同步各群公告，批量发送或删除指定公告。</p>
      </div>
      <div class="toolbar"><el-button @click="loadAll">刷新</el-button></div>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <div class="form-grid">
        <el-form-item label="目标群">
          <GroupSelector v-model="selectedGroups" :groups="groups" />
        </el-form-item>
      </div>
      <el-form-item label="公告内容">
        <el-input v-model="noticeContent" type="textarea" />
      </el-form-item>
      <div class="toolbar">
        <el-button type="primary" :disabled="!selectedGroups.length || !noticeContent" @click="send">批量发送</el-button>
        <el-button :disabled="!selectedGroups.length" @click="syncSelected">同步选中群</el-button>
      </div>
    </div>
    <div class="content-band">
      <el-table :data="notices" border>
        <el-table-column prop="group_id" label="群号" width="130" />
        <el-table-column prop="notice_id" label="公告 ID" width="190" />
        <el-table-column prop="title" label="标题" width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" min-width="240" show-overflow-tooltip />
        <el-table-column prop="synced_at" label="同步时间" width="210" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm title="确认删除这条公告？" @confirm="remove(row)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AdminLayout from '../components/AdminLayout.vue'
import GroupSelector from '../components/GroupSelector.vue'
import { api, type ManagedGroup } from '../api/client'

const groups = ref<ManagedGroup[]>([])
const notices = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const noticeContent = ref('')

async function loadAll() {
  const [groupRes, noticeRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/notices')])
  groups.value = groupRes.data
  notices.value = noticeRes.data
}
async function send() {
  const { data } = await api.post('/admin/notices/send', { group_ids: selectedGroups.value, content: noticeContent.value })
  ElMessage[data.ok ? 'success' : 'warning'](data.ok ? '发送完成' : '部分群发送失败')
  noticeContent.value = ''
  loadAll()
}
async function syncSelected() {
  for (const groupId of selectedGroups.value) {
    await api.post(`/admin/notices/sync/${groupId}`)
  }
  ElMessage.success('同步完成')
  loadAll()
}
async function remove(row: any) {
  const { data } = await api.post('/admin/notices/delete', { group_id: row.group_id, notice_ids: [row.notice_id] })
  ElMessage[data.ok ? 'success' : 'warning']('删除完成')
  loadAll()
}
onMounted(loadAll)
</script>
