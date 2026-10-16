<template>
  <v-card class="pa-6 surface-card" max-width="720">
    <h1 class="text-h5 mb-3">双因素认证</h1>
    <p class="mb-5">使用 Google Authenticator、Microsoft Authenticator 或其他兼容 TOTP 的验证器保护管理员登录。</p>
    <v-alert v-if="enabled" type="success" class="mb-4">双因素认证已启用。</v-alert>
    <template v-else>
      <v-btn v-if="!setup" color="primary" @click="beginSetup">开始绑定</v-btn>
      <template v-else>
        <p>在验证器中添加以下密钥，或手动输入密钥：</p>
        <img v-if="qrCode" :src="qrCode" alt="验证器绑定二维码" width="220" height="220" />
        <v-text-field :model-value="setup.secret" label="密钥" readonly />
        <v-text-field v-model="code" label="验证器中的 6 位验证码" inputmode="numeric" maxlength="6" />
        <v-btn color="primary" :loading="busy" @click="enable">验证并启用</v-btn>
      </template>
    </template>
    <template v-if="enabled">
      <v-text-field v-model="code" label="验证器中的 6 位验证码" inputmode="numeric" maxlength="6" />
      <v-btn color="error" :loading="busy" @click="disable">关闭双因素认证</v-btn>
    </template>
  </v-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'
import QRCode from 'qrcode'
import { api } from '../api/client'
import { notify } from '../stores/ui'

const enabled = ref(false)
const setup = ref<{ secret: string; otpauth_uri: string } | null>(null)
const qrCode = ref('')
const code = ref('')
const busy = ref(false)
onMounted(async () => {
  try { enabled.value = (await api.get<{ enabled: boolean }>('/auth/2fa/status')).data.enabled }
  catch { notify('无法读取账号安全状态', 'error') }
})
async function beginSetup() {
  try {
    setup.value = (await api.post<{ secret: string; otpauth_uri: string }>('/auth/2fa/setup')).data
    qrCode.value = await QRCode.toDataURL(setup.value.otpauth_uri, { width: 220, margin: 2 })
  }
  catch (error) { notify(axios.isAxiosError(error) ? error.response?.data?.detail ?? '绑定失败' : '绑定失败', 'error') }
}
async function enable() { await change('/auth/2fa/enable', true) }
async function disable() { await change('/auth/2fa/disable', false) }
async function change(path: string, turnOn: boolean) {
  busy.value = true
  try {
    await api.post(path, { code: code.value })
    enabled.value = turnOn; setup.value = null; qrCode.value = ''; code.value = ''
    notify(turnOn ? '双因素认证已启用' : '双因素认证已关闭', 'success')
  } catch (error) {
    notify(axios.isAxiosError(error) ? error.response?.data?.detail ?? '操作失败' : '操作失败', 'error')
  } finally { busy.value = false }
}
</script>
