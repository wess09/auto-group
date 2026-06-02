<template>
  <section class="login-page">
    <div class="login-panel">
      <h1 class="join-title">Auto Group</h1>
      <p class="join-meta">登录群管理后台</p>
      <n-form @submit.prevent="submit">
        <n-form-item label="账号">
          <n-input v-model:value="form.username" placeholder="admin" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="form.password" type="password" placeholder="admin123" />
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="submit">登录</n-button>
      </n-form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })

async function submit() {
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    localStorage.setItem('token', data.access_token)
    router.push('/admin')
  } catch (error: any) {
    message.error(error.response?.data?.detail ?? '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
