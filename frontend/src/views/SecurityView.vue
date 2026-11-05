<template>
  <v-card class="pa-6 surface-card" max-width="720">
    <h1 class="text-h5 mb-3">双因素认证</h1>
    <p class="mb-5">
      使用 Google Authenticator、Microsoft Authenticator 或其他兼容 TOTP 的验证器保护管理员登录。
    </p>
    <v-alert v-if="enabled" type="success" class="mb-4">双因素认证已启用。</v-alert>
    <template v-else>
      <v-btn v-if="!setup" color="primary" @click="beginSetup">开始绑定</v-btn>
      <template v-else>
        <p>在验证器中添加以下密钥，或手动输入密钥：</p>
        <img v-if="qrCode" :src="qrCode" alt="验证器绑定二维码" width="220" height="220" />
        <v-text-field :model-value="setup.secret" label="密钥" readonly />
        <v-text-field
          v-model="code"
          label="验证器中的 6 位验证码"
          inputmode="numeric"
          maxlength="6"
        />
        <v-btn color="primary" :loading="busy" @click="enable">验证并启用</v-btn>
      </template>
    </template>
    <template v-if="enabled">
      <v-text-field
        v-model="code"
        label="验证器中的 6 位验证码"
        inputmode="numeric"
        maxlength="6"
      />
      <v-btn color="error" :loading="busy" @click="disable">关闭双因素认证</v-btn>
    </template>
  </v-card>
  <v-card class="pa-6 surface-card mt-6" max-width="720">
    <h2 class="text-h5 mb-3">修改自己的密码</h2>
    <p class="mb-5">修改后，该账号的已有登录会失效，需要使用新密码重新登录。</p>
    <v-form @submit.prevent="changePassword">
      <v-text-field
        v-model="passwordForm.current_password"
        label="当前密码"
        type="password"
        autocomplete="current-password"
      />
      <v-text-field
        v-model="passwordForm.new_password"
        label="新密码"
        type="password"
        autocomplete="new-password"
        hint="8–128 位"
        persistent-hint
        class="mb-4"
      />
      <v-text-field
        v-model="confirmation"
        label="再次输入新密码"
        type="password"
        autocomplete="new-password"
      />
      <v-text-field
        v-if="enabled"
        v-model="passwordForm.totp_code"
        label="当前动态验证码"
        inputmode="numeric"
        maxlength="6"
      />
      <v-btn type="submit" :loading="passwordBusy">修改密码并重新登录</v-btn>
    </v-form>
  </v-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import QRCode from 'qrcode'
import { api, expireLogin } from '../api/client'
import { notify } from '../stores/ui'

const enabled = ref(false)
const setup = ref<{ secret: string; otpauth_uri: string } | null>(null)
const qrCode = ref('')
const code = ref('')
const busy = ref(false)
const passwordBusy = ref(false),
  confirmation = ref('')
const passwordForm = reactive({ current_password: '', new_password: '', totp_code: '' })
async function changePassword() {
  if (
    !passwordForm.current_password ||
    passwordForm.new_password.length < 8 ||
    passwordForm.new_password.length > 128 ||
    passwordForm.new_password !== confirmation.value
  ) {
    notify('请填写当前密码，并确保新密码为 8–128 位且两次输入一致', 'error')
    return
  }
  passwordBusy.value = true
  try {
    await api.post('/auth/password', passwordForm)
    Object.assign(passwordForm, { current_password: '', new_password: '', totp_code: '' })
    confirmation.value = ''
    notify('密码已修改，请重新登录', 'success')
    expireLogin()
  } catch (error) {
    notify(
      axios.isAxiosError(error) ? (error.response?.data?.detail ?? '修改失败') : '修改失败',
      'error',
    )
  } finally {
    passwordBusy.value = false
  }
}
onMounted(async () => {
  try {
    enabled.value = (await api.get<{ enabled: boolean }>('/auth/2fa/status')).data.enabled
  } catch {
    notify('无法读取账号安全状态', 'error')
  }
})
async function beginSetup() {
  try {
    setup.value = (await api.post<{ secret: string; otpauth_uri: string }>('/auth/2fa/setup')).data
    qrCode.value = await QRCode.toDataURL(setup.value.otpauth_uri, { width: 220, margin: 2 })
  } catch (error) {
    notify(
      axios.isAxiosError(error) ? (error.response?.data?.detail ?? '绑定失败') : '绑定失败',
      'error',
    )
  }
}
async function enable() {
  await change('/auth/2fa/enable', true)
}
async function disable() {
  await change('/auth/2fa/disable', false)
}
async function change(path: string, turnOn: boolean) {
  busy.value = true
  try {
    await api.post(path, { code: code.value })
    enabled.value = turnOn
    setup.value = null
    qrCode.value = ''
    code.value = ''
    notify(turnOn ? '双因素认证已启用' : '双因素认证已关闭', 'success')
  } catch (error) {
    notify(
      axios.isAxiosError(error) ? (error.response?.data?.detail ?? '操作失败') : '操作失败',
      'error',
    )
  } finally {
    busy.value = false
  }
}
</script>
