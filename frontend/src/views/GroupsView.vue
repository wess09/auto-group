<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">群配置</h1>
        <p class="page-subtitle">配置优先级、容量、入群链接和分流提示。</p>
      </div>
      <div class="toolbar">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新增群</el-button>
      </div>
    </div>
    <div class="content-band">
      <el-table
        ref="tableRef"
        :data="groups"
        v-loading="ordering"
        :row-key="rowKey"
        border
      >
        <el-table-column width="48" align="center">
          <template #default>
            <button
              class="drag-handle"
              title="拖动调整优先级"
              type="button"
              aria-label="拖动调整优先级"
            >
              <el-icon><Rank /></el-icon>
            </button>
          </template>
        </el-table-column>
        <el-table-column prop="group_id" label="群号" width="130" />
        <el-table-column prop="name" label="群名" min-width="150" />
        <el-table-column label="优先级" width="140">
          <template #default="{ row, $index }">
            <span class="priority-pill">{{ row.priority }} · 第 {{ $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="人数" width="130">
          <template #default="{ row }">
            {{ row.current_members }}{{ row.max_members ? ` / ${row.max_members}` : '' }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="(value: boolean) => toggle(row, value)" />
          </template>
        </el-table-column>
        <el-table-column prop="join_url" label="入群链接" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" @click="sync(row.group_id)">刷新人数</el-button>
              <el-popconfirm title="确认删除这个群配置？" @confirm="remove(row.group_id)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="showModal" title="群配置" width="min(720px, 96vw)">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="群号"><el-input-number v-model="form.group_id" :disabled="editing" /></el-form-item>
          <el-form-item label="群名"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="优先级"><el-input-number v-model="form.priority" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
          <el-form-item label="最大人数"><el-input-number v-model="form.max_members" /></el-form-item>
          <el-form-item label="当前人数"><el-input-number v-model="form.current_members" /></el-form-item>
        </div>
        <el-form-item label="入群链接"><el-input v-model="form.join_url" /></el-form-item>
        <el-form-item label="分流拒绝提示">
          <el-input v-model="form.redirect_message_template" type="textarea" />
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
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import Sortable from 'sortablejs'
import { ElMessage } from 'element-plus'
import { Rank } from '@element-plus/icons-vue'
import AdminLayout from '../components/AdminLayout.vue'
import { api, type ManagedGroup } from '../api/client'

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

async function load() {
  const { data } = await api.get('/admin/groups')
  groups.value = data
  await nextTick()
  bindSortable()
}

function bindSortable() {
  const tableEl = (tableRef.value as { $el?: HTMLElement } | null)?.$el
  const tbody = tableEl?.querySelector('.el-table__body-wrapper tbody') as HTMLElement | null
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
    ElMessage.success('优先级已更新')
  } catch (error) {
    groups.value = before
    ElMessage.error('优先级保存失败，已恢复原顺序')
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
  ElMessage.success('已保存')
  showModal.value = false
  load()
}

async function toggle(row: ManagedGroup, enabled: boolean) {
  await api.patch(`/admin/groups/${row.group_id}`, { enabled })
  row.enabled = enabled
}

async function sync(groupId: number) {
  const { data } = await api.post(`/admin/groups/${groupId}/sync`)
  ElMessage.success(data.message)
  load()
}

async function remove(groupId: number) {
  await api.delete(`/admin/groups/${groupId}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
onBeforeUnmount(() => sortable.value?.destroy())
</script>
