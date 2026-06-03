<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">加群黑名单</h1>
        <p class="page-subtitle">黑名单 QQ 的所有加群申请会被直接拒绝。</p>
      </div>
      <div class="toolbar">
        <n-button @click="load">刷新</n-button>
        <n-button type="primary" @click="openCreate">新增黑名单</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table :columns="columns" :data="items" />
    </div>
    <n-modal v-model:show="showModal" preset="card" title="加群黑名单" style="width: min(640px, 96vw)">
      <n-form>
        <div class="form-grid">
          <n-form-item label="QQ"><n-input-number v-model:value="form.user_id" :disabled="editing" /></n-form-item>
          <n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item>
        </div>
        <n-form-item label="拒绝原因"><n-input v-model:value="form.reason" type="textarea" /></n-form-item>
        <n-form-item label="备注"><n-input v-model:value="form.note" type="textarea" /></n-form-item>
        <n-button type="primary" @click="save">保存</n-button>
      </n-form>
    </n-modal>
  </AdminLayout>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NButton, NPopconfirm, NSpace, NSwitch, useMessage, type DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type JoinBlacklistItem } from '../api/client'

const message = useMessage()
const items = ref<JoinBlacklistItem[]>([])
const showModal = ref(false)
const editing = ref(false)
const editingId = ref<number | null>(null)
const defaultForm = {
  user_id: 0,
  enabled: true,
  reason: '你已被加入黑名单，无法申请入群。',
  note: ''
}
const form = reactive({ ...defaultForm })

const columns: DataTableColumns<JoinBlacklistItem> = [
  { title: 'QQ', key: 'user_id', width: 140 },
  {
    title: '启用',
    key: 'enabled',
    width: 90,
    render: (row) => h(NSwitch, { value: row.enabled, 'onUpdate:value': (value: boolean) => toggle(row, value) })
  },
  { title: '拒绝原因', key: 'reason', ellipsis: { tooltip: true } },
  { title: '备注', key: 'note', ellipsis: { tooltip: true } },
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
  const { data } = await api.get('/admin/join-blacklist')
  items.value = data
}

function openCreate() {
  Object.assign(form, defaultForm)
  editing.value = false
  editingId.value = null
  showModal.value = true
}

function openEdit(row: JoinBlacklistItem) {
  Object.assign(form, row)
  editing.value = true
  editingId.value = row.id
  showModal.value = true
}

async function save() {
  if (editing.value) {
    await api.patch(`/admin/join-blacklist/${editingId.value}`, form)
  } else {
    await api.post('/admin/join-blacklist', form)
  }
  message.success('已保存')
  showModal.value = false
  load()
}

async function toggle(row: JoinBlacklistItem, enabled: boolean) {
  await api.patch(`/admin/join-blacklist/${row.id}`, { enabled })
  row.enabled = enabled
}

async function remove(id: number) {
  await api.delete(`/admin/join-blacklist/${id}`)
  message.success('已删除')
  load()
}

onMounted(load)
</script>
