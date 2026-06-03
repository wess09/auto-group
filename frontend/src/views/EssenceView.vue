<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">精华管理</h1>
        <p class="page-subtitle">把指定内容发送到单群或多群，并自动设为精华。</p>
      </div>
      <el-button @click="loadAll">刷新</el-button>
    </div>
    <div class="content-band" style="margin-bottom: 16px">
      <el-form-item label="目标群">
        <GroupSelector v-model="selectedGroups" :groups="groups" />
      </el-form-item>
      <el-form-item label="精华内容">
        <el-input v-model="content" type="textarea" />
      </el-form-item>
      <div class="toolbar">
        <el-button type="primary" :disabled="!selectedGroups.length || !content" @click="create">发送并设精</el-button>
        <el-button :disabled="!selectedGroups.length" @click="syncSelected">同步选中群精华</el-button>
      </div>
    </div>
    <div class="content-band">
      <el-table :data="essence" border>
        <el-table-column prop="group_id" label="群号" width="130" />
        <el-table-column prop="message_id" label="消息 ID" width="130" />
        <el-table-column prop="sender_id" label="发送者" width="130" />
        <el-table-column prop="content" label="内容" min-width="240" show-overflow-tooltip />
        <el-table-column prop="synced_at" label="同步时间" width="210" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-popconfirm title="确认移出精华？" @confirm="remove(row)">
              <template #reference>
                <el-button size="small" type="danger">移出精华</el-button>
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
const essence = ref<any[]>([])
const selectedGroups = ref<number[]>([])
const content = ref('')

async function loadAll() {
  const [groupRes, essenceRes] = await Promise.all([api.get('/admin/groups'), api.get('/admin/essence')])
  groups.value = groupRes.data
  essence.value = essenceRes.data
}
async function create() {
  const { data } = await api.post('/admin/essence/create', { group_ids: selectedGroups.value, content: content.value })
  ElMessage[data.ok ? 'success' : 'warning']('任务完成')
  content.value = ''
  loadAll()
}
async function syncSelected() {
  for (const groupId of selectedGroups.value) await api.post(`/admin/essence/sync/${groupId}`)
  ElMessage.success('同步完成')
  loadAll()
}
async function remove(row: any) {
  await api.post('/admin/essence/delete', { group_id: row.group_id, message_ids: [row.message_id] })
  ElMessage.success('已移出')
  loadAll()
}
onMounted(loadAll)
</script>
