<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">入群规则</h1>
        <p class="page-subtitle">按群配置答案规则，支持关键词、完全匹配和正则。</p>
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
        <el-table-column prop="match_mode" label="方式" width="120" />
        <el-table-column prop="logic_mode" label="逻辑" width="120" />
        <el-table-column label="规则" min-width="240">
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
    <el-dialog v-model="showModal" title="入群规则" width="min(680px, 96vw)">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="适用群号"><el-input-number v-model="form.group_id" placeholder="留空为全局" /></el-form-item>
          <el-form-item label="匹配方式"><el-select v-model="form.match_mode" :options="matchOptions" /></el-form-item>
          <el-form-item label="逻辑"><el-select v-model="form.logic_mode" :options="logicOptions" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        </div>
        <el-form-item label="规则内容">
          <el-input v-model="patternsText" type="textarea" placeholder="每行一个关键词或正则" />
        </el-form-item>
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
import { api, type AnswerRule } from '../api/client'

const rules = ref<AnswerRule[]>([])
const showModal = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<any>({
  name: '',
  enabled: true,
  group_id: null,
  match_mode: 'contains',
  logic_mode: 'any',
  patterns: []
})
const patternsText = computed({
  get: () => form.patterns.join('\n'),
  set: (value: string) => {
    form.patterns = value.split('\n').map((item) => item.trim()).filter(Boolean)
  }
})
const matchOptions = [
  { label: '包含关键词', value: 'contains' },
  { label: '完全匹配', value: 'exact' },
  { label: '正则匹配', value: 'regex' }
]
const logicOptions = [
  { label: '任一命中', value: 'any' },
  { label: '全部命中', value: 'all' }
]
async function load() {
  const { data } = await api.get('/admin/rules')
  rules.value = data
}
function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', enabled: true, group_id: null, match_mode: 'contains', logic_mode: 'any', patterns: [] })
  showModal.value = true
}
function openEdit(row: AnswerRule) {
  editingId.value = row.id
  Object.assign(form, { ...row })
  showModal.value = true
}
async function save() {
  if (editingId.value) await api.patch(`/admin/rules/${editingId.value}`, form)
  else await api.post('/admin/rules', form)
  ElMessage.success('已保存')
  showModal.value = false
  load()
}
async function remove(id: number) {
  await api.delete(`/admin/rules/${id}`)
  ElMessage.success('已删除')
  load()
}
onMounted(load)
</script>
