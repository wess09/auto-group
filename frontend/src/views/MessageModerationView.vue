<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">消息审查</h1>
        <p class="page-subtitle">按群配置正则规则，命中后自动撤回、禁言或同时处理。</p>
      </div>
      <div class="toolbar">
        <n-button @click="load">刷新</n-button>
        <n-button type="primary" @click="openCreate">新增规则</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table :columns="columns" :data="rules" />
    </div>
    <n-modal v-model:show="showModal" preset="card" title="消息审查规则" style="width: min(720px, 96vw)">
      <n-form>
        <div class="form-grid">
          <n-form-item label="名称"><n-input v-model:value="form.name" /></n-form-item>
          <n-form-item label="适用群号"><n-input-number v-model:value="form.group_id" placeholder="留空为全局" /></n-form-item>
          <n-form-item label="动作"><n-select v-model:value="form.action" :options="actionOptions" /></n-form-item>
          <n-form-item label="禁言秒数"><n-input-number v-model:value="form.mute_duration_seconds" :min="1" /></n-form-item>
          <n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item>
        </div>
        <n-form-item label="正则表达式">
          <n-input v-model:value="patternsText" type="textarea" placeholder="每行一个正则表达式" />
        </n-form-item>
        <n-form-item label="备注"><n-input v-model:value="form.note" type="textarea" /></n-form-item>
        <n-button type="primary" @click="save">保存</n-button>
      </n-form>
    </n-modal>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NTag, useMessage, type DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type MessageModerationRule } from '../api/client'

const message = useMessage()
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
const actionLabels: Record<MessageModerationRule['action'], string> = {
  recall: '撤回',
  mute: '禁言',
  recall_and_mute: '撤回并禁言'
}
const columns: DataTableColumns<MessageModerationRule> = [
  { title: '名称', key: 'name' },
  { title: '适用群', key: 'group_id', width: 120, render: (row) => row.group_id ?? '全局' },
  {
    title: '动作',
    key: 'action',
    width: 140,
    render: (row) => h(NTag, { type: row.action === 'recall' ? 'info' : 'warning' }, { default: () => actionLabels[row.action] })
  },
  {
    title: '禁言',
    key: 'mute_duration_seconds',
    width: 110,
    render: (row) => row.action === 'recall' ? '-' : `${row.mute_duration_seconds} 秒`
  },
  { title: '正则', key: 'patterns', render: (row) => row.patterns.map((pattern) => h(NTag, { style: 'margin-right: 6px' }, { default: () => pattern })) },
  { title: '启用', key: 'enabled', width: 80, render: (row) => row.enabled ? '是' : '否' },
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
  message.success('已保存')
  showModal.value = false
  load()
}

async function remove(id: number) {
  await api.delete(`/admin/message-moderation-rules/${id}`)
  message.success('已删除')
  load()
}

onMounted(load)
</script>
