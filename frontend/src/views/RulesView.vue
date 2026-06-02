<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">入群规则</h1>
        <p class="page-subtitle">按群配置答案规则，支持关键词、完全匹配和正则。</p>
      </div>
      <div class="toolbar">
        <n-button @click="load">刷新</n-button>
        <n-button type="primary" @click="openCreate">新增规则</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table :columns="columns" :data="rules" />
    </div>
    <n-modal v-model:show="showModal" preset="card" title="入群规则" style="width: min(680px, 96vw)">
      <n-form>
        <div class="form-grid">
          <n-form-item label="名称"><n-input v-model:value="form.name" /></n-form-item>
          <n-form-item label="适用群号"><n-input-number v-model:value="form.group_id" placeholder="留空为全局" /></n-form-item>
          <n-form-item label="匹配方式"><n-select v-model:value="form.match_mode" :options="matchOptions" /></n-form-item>
          <n-form-item label="逻辑"><n-select v-model:value="form.logic_mode" :options="logicOptions" /></n-form-item>
          <n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item>
        </div>
        <n-form-item label="规则内容">
          <n-input v-model:value="patternsText" type="textarea" placeholder="每行一个关键词或正则" />
        </n-form-item>
        <n-button type="primary" @click="save">保存</n-button>
      </n-form>
    </n-modal>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type AnswerRule } from '../api/client'

const message = useMessage()
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
const columns: DataTableColumns<AnswerRule> = [
  { title: '名称', key: 'name' },
  { title: '适用群', key: 'group_id', render: (row) => row.group_id ?? '全局' },
  { title: '方式', key: 'match_mode' },
  { title: '逻辑', key: 'logic_mode' },
  { title: '规则', key: 'patterns', render: (row) => row.patterns.map((p) => h(NTag, { style: 'margin-right: 6px' }, { default: () => p })) },
  { title: '启用', key: 'enabled', render: (row) => row.enabled ? '是' : '否' },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (row) => h(NSpace, [
      h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
      h(NPopconfirm, { onPositiveClick: () => remove(row.id) }, {
        trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
        default: () => '确认删除？'
      })
    ])
  }
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
  message.success('已保存')
  showModal.value = false
  load()
}
async function remove(id: number) {
  await api.delete(`/admin/rules/${id}`)
  message.success('已删除')
  load()
}
onMounted(load)
</script>
