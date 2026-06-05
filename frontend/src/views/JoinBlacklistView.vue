<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">加群黑名单</h1>
        <p class="page-subtitle">黑名单 QQ 的所有加群申请会被直接拒绝。</p>
      </div>
      <div class="toolbar">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新增黑名单</el-button>
      </div>
    </div>
    <div class="content-band" v-loading="loading" element-loading-text="正在加载黑名单列表..." style="min-height: 200px;">
      <el-table :data="items" border>
        <el-table-column prop="user_id" label="QQ" width="140" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="(value: boolean) => toggle(row, value)" />
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="拒绝原因" min-width="220" show-overflow-tooltip />
        <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
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
    <el-dialog v-model="showModal" title="加群黑名单" width="min(640px, 96vw)">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="QQ"><el-input-number v-model="form.user_id" :disabled="editing" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        </div>
        <el-form-item label="拒绝原因"><el-input v-model="form.reason" type="textarea" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showModal = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AdminLayout from '../components/AdminLayout.vue'
import { api, getApiErrorMessage, type JoinBlacklistItem } from '../api/client'

const items = ref<JoinBlacklistItem[]>([])
const showModal = ref(false)
const editing = ref(false)
const editingId = ref<number | null>(null)
const loading = ref(true)
const saving = ref(false)
const defaultForm = {
  user_id: 0,
  enabled: true,
  reason: '你已被加入黑名单，无法申请入群。',
  note: ''
}
const form = reactive({ ...defaultForm })

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/join-blacklist')
    items.value = data
  } catch (error: any) {
    ElMessage.error('加载黑名单失败：' + getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
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
  saving.value = true
  try {
    if (editing.value) {
      await api.patch(`/admin/join-blacklist/${editingId.value}`, form)
    } else {
      await api.post('/admin/join-blacklist', form)
    }
    ElMessage.success('已保存')
    showModal.value = false
    load()
  } catch (error) {
    ElMessage.error('保存黑名单失败：' + getApiErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function toggle(row: JoinBlacklistItem, enabled: boolean) {
  try {
    await api.patch(`/admin/join-blacklist/${row.id}`, { enabled })
    row.enabled = enabled
  } catch (error) {
    row.enabled = !enabled
    ElMessage.error('更新黑名单失败：' + getApiErrorMessage(error))
  }
}

async function remove(id: number) {
  try {
    await api.delete(`/admin/join-blacklist/${id}`)
    ElMessage.success('已删除')
    load()
  } catch (error) {
    ElMessage.error('删除黑名单失败：' + getApiErrorMessage(error))
  }
}

onMounted(load)
</script>
