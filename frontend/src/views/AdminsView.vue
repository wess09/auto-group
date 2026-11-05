<!-- Primary: administrator identity and status; secondary: role/security; tertiary: last login.
     One primary action creates an account. Reuse MD3 surface/primary/error roles, pa-6/mb-4 spacing,
     and existing ResourceTable/dialog patterns; accounts are disabled to preserve audit history. -->
<template>
  <AdminLayout>
    <PageHeader
      title="管理员管理"
      subtitle="为每位管理员创建独立账号。停用、调整权限和重置凭据会使该账号的已有登录失效。"
    >
      <v-btn :prepend-icon="mdiPlus" @click="openCreate">新增管理员</v-btn>
    </PageHeader>
    <ResourceTable ref="table" resource="admins" :headers="headers">
      <template #actions="{ row }">
        <div class="d-flex ga-1 flex-wrap py-2">
          <v-btn variant="text" size="small" @click="openEdit(row)">编辑</v-btn>
          <v-btn variant="text" size="small" @click="openPassword(row)">重置密码</v-btn>
          <v-btn variant="text" size="small" @click="resetTarget = row">重置验证器</v-btn>
        </div>
      </template>
    </ResourceTable>
    <v-dialog v-model="dialog" max-width="560" scrollable @after-leave="form.password = ''">
      <v-card :title="editing ? '编辑管理员' : '新增管理员'">
        <v-card-text>
          <v-form ref="formRef" @submit.prevent="save">
            <v-text-field
              v-model="form.username"
              label="登录账号"
              :disabled="!!editing"
              :rules="[required]"
              hint="3–64 位，可使用字母、数字、汉字、下划线、点、@ 和短横线；创建后不可修改"
              persistent-hint
              class="mb-4"
            />
            <v-text-field
              v-model="form.display_name"
              label="姓名或备注名"
              maxlength="80"
              class="mb-2"
            />
            <v-select
              v-model="form.role"
              label="权限"
              :items="roles"
              :disabled="editing === user.profile?.id"
              class="mb-2"
            />
            <v-text-field
              v-if="!editing"
              v-model="form.password"
              label="初始密码"
              type="password"
              autocomplete="new-password"
              :rules="[passwordRule]"
              hint="8–128 位，密码不会显示在日志中"
              persistent-hint
              class="mb-4"
            />
            <v-switch
              v-if="editing"
              v-model="form.enabled"
              label="允许登录"
              :disabled="editing === user.profile?.id"
              color="primary"
              hide-details
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">取消</v-btn>
          <v-btn :loading="busy" @click="save">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="passwordDialog" max-width="480" @after-leave="newPassword = ''">
      <v-card title="重置管理员密码">
        <v-card-text>
          <p class="mb-4">账号：{{ passwordTarget?.username }}。重置后需要重新登录。</p>
          <v-text-field
            v-model="newPassword"
            label="新密码"
            type="password"
            autocomplete="new-password"
            :rules="[passwordRule]"
            hint="8–128 位"
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="passwordDialog = false">取消</v-btn>
          <v-btn :loading="busy" @click="resetPassword">确认重置</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      :model-value="!!resetTarget"
      max-width="480"
      @update:model-value="!$event && (resetTarget = null)"
    >
      <v-card
        title="重置双因素认证"
        :text="`解除 ${resetTarget?.username} 的验证器绑定并使已有登录失效。该管理员之后可在账号安全中重新绑定。`"
      >
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="resetTarget = null">取消</v-btn>
          <v-btn color="error" :loading="busy" @click="resetTotp">确认重置</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AdminLayout>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { mdiPlus } from '@mdi/js'
import AdminLayout from '../components/AdminLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import ResourceTable from '../components/ResourceTable.vue'
import { socket } from '../api/client'
import type { DataRow } from '../api/types'
import { notify, report } from '../stores/ui'
import { useUserStore } from '../stores/modules/user'

const user = useUserStore()
const table = ref<InstanceType<typeof ResourceTable>>()
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> }>()
const dialog = ref(false),
  passwordDialog = ref(false),
  busy = ref(false),
  editing = ref<number | null>(null)
const form = reactive({
  username: '',
  display_name: '',
  role: 'admin' as 'admin' | 'superadmin',
  enabled: true,
  password: '',
})
const passwordTarget = ref<DataRow | null>(null),
  resetTarget = ref<DataRow | null>(null),
  newPassword = ref('')
const required = (value: string) => !!value || '请填写此项'
const passwordRule = (value: string) =>
  (value.length >= 8 && value.length <= 128) || '密码长度须为 8–128 位'
const roles = [
  { title: '普通管理员：群管理与操作日志', value: 'admin' },
  { title: '超级管理员：另可管理后台账号', value: 'superadmin' },
]
const headers = [
  ['ID', 'id'],
  ['账号', 'username'],
  ['姓名', 'display_name'],
  ['权限', 'role'],
  ['允许登录', 'enabled'],
  ['双因素认证', 'totp_enabled'],
  ['最近登录', 'last_login_at'],
  ['登录 IP', 'last_login_ip'],
  ['操作', 'actions'],
].map(([title, key]) => ({ title, key, sortable: false }))
function openCreate() {
  editing.value = null
  Object.assign(form, {
    username: '',
    display_name: '',
    role: 'admin',
    enabled: true,
    password: '',
  })
  dialog.value = true
}
async function openEdit(row: DataRow) {
  try {
    const data = await socket.request('admins.get', { id: row.id })
    editing.value = data.id
    Object.assign(form, data, { password: '' })
    dialog.value = true
  } catch (error) {
    report(error)
  }
}
function openPassword(row: DataRow) {
  passwordTarget.value = row
  newPassword.value = ''
  passwordDialog.value = true
}
async function save() {
  if (!(await formRef.value?.validate())?.valid) return
  busy.value = true
  try {
    if (editing.value)
      await socket.request('admins.update', {
        id: editing.value,
        display_name: form.display_name,
        role: form.role,
        enabled: form.enabled,
      })
    else
      await socket.request('admins.create', {
        username: form.username,
        password: form.password,
        display_name: form.display_name,
        role: form.role,
      })
    dialog.value = false
    form.password = ''
    notify('管理员已保存', 'success')
    await table.value?.refetch()
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function resetPassword() {
  if (passwordRule(newPassword.value) !== true || !passwordTarget.value) return
  busy.value = true
  try {
    await socket.request('admins.reset-password', {
      id: passwordTarget.value.id,
      password: newPassword.value,
    })
    passwordDialog.value = false
    newPassword.value = ''
    notify('密码已重置', 'success')
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
async function resetTotp() {
  if (!resetTarget.value) return
  busy.value = true
  try {
    await socket.request('admins.reset-2fa', { id: resetTarget.value.id })
    resetTarget.value = null
    notify('双因素认证已重置', 'success')
    await table.value?.refetch()
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
</script>
