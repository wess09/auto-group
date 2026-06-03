<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">消息审查</h1>
        <p class="page-subtitle">按群配置正则规则，命中后自动撤回、禁言或同时处理。</p>
      </div>
      <div class="toolbar">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新增规则</el-button>
      </div>
    </div>
    <div class="content-band">
      <el-table :data="rules" border>
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="适用群" width="120">
          <template #default="{ row }">{{ row.group_id ?? '全局' }}</template>
        </el-table-column>
        <el-table-column label="动作" width="140">
          <template #default="{ row }">
            <el-tag :type="row.action === 'recall' ? 'primary' : 'warning'">{{ actionLabels[row.action] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="禁言" width="120">
          <template #default="{ row }">{{ row.action === 'recall' ? '-' : `${row.mute_duration_seconds} 秒` }}</template>
        </el-table-column>
        <el-table-column label="正则" min-width="240">
          <template #default="{ row }">
            <el-tag v-for="pattern in row.patterns" :key="pattern" class="tag-gap">
              {{ pattern }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-popconfirm title="确认删除？" @confirm="remove(row.id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="showModal" title="消息审查规则" width="min(720px, 96vw)">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="适用群号"><el-input-number v-model="form.group_id" placeholder="留空为全局" /></el-form-item>
          <el-form-item label="动作"><el-select v-model="form.action" :options="actionOptions" /></el-form-item>
          <el-form-item label="禁言秒数"><el-input-number v-model="form.mute_duration_seconds" :min="1" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        </div>
        <el-form-item label="正则表达式">
          <el-input v-model="patternsText" type="textarea" placeholder="每行一个正则表达式" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showModal = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type MessageModerationRule } from '../api/client'

const rules = ref<MessageModerationRule[]>([])
const showModal = ref(false)
const editingId = ref<number | null>(null)
const defaultForm = {
  name: '',
  enabled: true,
  group_id: null as number | null,
  patterns: [] as string[],
  action: 'recall' as MessageModerationRule['action'],
  mute_duration_seconds: 600,
  note: ''
}
const form = reactive({ ...defaultForm })
const patternsText = computed({
  get: () => form.patterns.join('\n'),
  set: (value: string) => {
    form.patterns = value.split('\n').map((item) => item.trim()).filter(Boolean)
  }
})
const actionOptions = [
  { label: '撤回', value: 'recall' },
  { label: '禁言', value: 'mute' },
  { label: '撤回并禁言', value: 'recall_and_mute' }
]
const actionLabels: Record<string, string> = {
  recall: '撤回',
  mute: '禁言',
  recall_and_mute: '撤回并禁言'
}
async function load() {
  const { data } = await api.get('/admin/message-moderation-rules')
  rules.value = data
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { ...defaultForm, patterns: [] })
  showModal.value = true
}

function openEdit(row: MessageModerationRule) {
  editingId.value = row.id
  Object.assign(form, { ...row, patterns: [...row.patterns] })
  showModal.value = true
}

async function save() {
  if (editingId.value) {
    await api.patch(`/admin/message-moderation-rules/${editingId.value}`, form)
  } else {
    await api.post('/admin/message-moderation-rules', form)
  }
  ElMessage.success('已保存')
  showModal.value = false
  load()
}

async function remove(id: number) {
  await api.delete(`/admin/message-moderation-rules/${id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>
