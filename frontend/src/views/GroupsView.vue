<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">群配置</h1>
        <p class="page-subtitle">配置优先级、容量、入群链接和分流提示。</p>
      </div>
      <div class="toolbar">
        <n-button @click="load">刷新</n-button>
        <n-button type="primary" @click="openCreate">新增群</n-button>
      </div>
    </div>
    <div class="content-band">
      <n-data-table
        ref="tableRef"
        :columns="columns"
        :data="groups"
        :loading="ordering"
        :row-key="rowKey"
      />
    </div>
    <n-modal v-model:show="showModal" preset="card" title="群配置" style="width: min(720px, 96vw)">
      <n-form>
        <div class="form-grid">
          <n-form-item label="群号"><n-input-number v-model:value="form.group_id" :disabled="editing" /></n-form-item>
          <n-form-item label="群名"><n-input v-model:value="form.name" /></n-form-item>
          <n-form-item label="优先级"><n-input-number v-model:value="form.priority" /></n-form-item>
          <n-form-item label="启用"><n-switch v-model:value="form.enabled" /></n-form-item>
          <n-form-item label="最大人数"><n-input-number v-model:value="form.max_members" /></n-form-item>
          <n-form-item label="当前人数"><n-input-number v-model:value="form.current_members" /></n-form-item>
        </div>
        <n-form-item label="入群链接"><n-input v-model:value="form.join_url" /></n-form-item>
        <n-form-item label="分流拒绝提示">
          <n-input v-model:value="form.redirect_message_template" type="textarea" />
        </n-form-item>
        <n-form-item label="备注"><n-input v-model:value="form.note" type="textarea" /></n-form-item>
        <n-button type="primary" @click="save">保存</n-button>
      </n-form>
    </n-modal>
  </AdminLayout>
</template>

<script setup lang="ts">
import { h, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import Sortable from 'sortablejs'
import {
  NButton,
  NIcon,
  NPopconfirm,
  NSpace,
  NSwitch,
  useMessage,
  type DataTableColumns
} from 'naive-ui'
import { GripVertical } from '@vicons/tabler'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type ManagedGroup } from '../api/client'

const message = useMessage()
const groups = ref<ManagedGroup[]>([])
const tableRef = ref<unknown>(null)
const ordering = ref(false)
const sortable = ref<Sortable | null>(null)
const showModal = ref(false)
const editing = ref(false)
const defaultForm = {
  group_id: 0,
  name: '',
  priority: 100,
  enabled: true,
  max_members: 0,
  current_members: 0,
  join_url: '',
  redirect_message_template: '请申请推荐群：{group_name}（{group_id}）。入群链接：{join_url}',
  note: ''
}
const form = reactive({ ...defaultForm })

function rowKey(row: ManagedGroup) {
  return row.group_id
}

const columns: DataTableColumns<ManagedGroup> = [
  {
    title: '',
    key: 'drag',
    width: 44,
    render: () =>
      h(
        'button',
        {
          class: 'drag-handle',
          title: '拖动调整优先级',
          type: 'button',
          'aria-label': '拖动调整优先级'
        },
        [h(NIcon, { size: 18 }, { default: () => h(GripVertical) })]
      )
  },
  { title: '群号', key: 'group_id', width: 130 },
  { title: '群名', key: 'name' },
  {
    title: '优先级',
    key: 'priority',
    width: 120,
    render: (row, index) =>
      h('span', { class: 'priority-pill' }, `${row.priority} · 第 ${index + 1}`)
  },
  { title: '人数', key: 'members', render: (row) => `${row.current_members}${row.max_members ? ` / ${row.max_members}` : ''}` },
  { title: '启用', key: 'enabled', width: 90, render: (row) => h(NSwitch, { value: row.enabled, 'onUpdate:value': (value: boolean) => toggle(row, value) }) },
  { title: '入群链接', key: 'join_url', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    render: (row) =>
      h(NSpace, [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', onClick: () => sync(row.group_id) }, { default: () => '刷新人数' }),
        h(NPopconfirm, { onPositiveClick: () => remove(row.group_id) }, {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          default: () => '确认删除这个群配置？'
        })
      ])
  }
]

async function load() {
  const { data } = await api.get('/admin/groups')
  groups.value = data
  await nextTick()
  bindSortable()
}

function bindSortable() {
  const tableEl = (tableRef.value as { $el?: HTMLElement } | null)?.$el
  const tbody = tableEl?.querySelector('.n-data-table-table tbody') as HTMLElement | null
  if (!tbody) return
  sortable.value?.destroy()
  sortable.value = Sortable.create(tbody, {
    animation: 160,
    handle: '.drag-handle',
    draggable: 'tr',
    ghostClass: 'drag-row-ghost',
    chosenClass: 'drag-row-chosen',
    dragClass: 'drag-row-active',
    onEnd: async ({ oldIndex, newIndex }) => {
      if (oldIndex == null || newIndex == null || oldIndex === newIndex) return
      await reorderGroups(oldIndex, newIndex)
    }
  })
}

async function reorderGroups(oldIndex: number, newIndex: number) {
  const before = groups.value.map((group) => ({ ...group }))
  const nextGroups = [...groups.value]
  const [moved] = nextGroups.splice(oldIndex, 1)
  nextGroups.splice(newIndex, 0, moved)
  groups.value = applyPriorityByOrder(nextGroups)
  ordering.value = true
  try {
    await Promise.all(
      groups.value.map((group) =>
        api.patch(`/admin/groups/${group.group_id}`, { priority: group.priority })
      )
    )
    message.success('优先级已更新')
  } catch (error) {
    groups.value = before
    message.error('优先级保存失败，已恢复原顺序')
  } finally {
    ordering.value = false
    await nextTick()
    bindSortable()
  }
}

function applyPriorityByOrder(list: ManagedGroup[]) {
  const base = Math.max(1000, list.length * 10)
  return list.map((group, index) => ({
    ...group,
    priority: base - index * 10
  }))
}

function openCreate() {
  Object.assign(form, defaultForm)
  editing.value = false
  showModal.value = true
}

function openEdit(row: ManagedGroup) {
  Object.assign(form, row)
  editing.value = true
  showModal.value = true
}

async function save() {
  if (editing.value) {
    await api.patch(`/admin/groups/${form.group_id}`, form)
  } else {
    await api.post('/admin/groups', form)
  }
  message.success('已保存')
  showModal.value = false
  load()
}

async function toggle(row: ManagedGroup, enabled: boolean) {
  await api.patch(`/admin/groups/${row.group_id}`, { enabled })
  row.enabled = enabled
}

async function sync(groupId: number) {
  const { data } = await api.post(`/admin/groups/${groupId}/sync`)
  message.success(data.message)
  load()
}

async function remove(groupId: number) {
  await api.delete(`/admin/groups/${groupId}`)
  message.success('已删除')
  load()
}

onMounted(load)
onBeforeUnmount(() => sortable.value?.destroy())
</script>
