<template>
  <main class="auth-wrap">
    <v-card class="auth-card surface-card">
      <v-icon :icon="mdiAccountGroupOutline" size="40" color="primary" class="mb-6" />
      <h1>找到你的群</h1>
      <p>Auto Group 会根据优先级与剩余容量推荐适合加入的群。</p>
      <v-progress-linear v-if="loading" indeterminate class="mb-4" />
      <QueryError :error="error" @retry="load" />
      <template v-if="group">
        <h2 class="text-title-large mb-3">
          {{ group.available ? group.group_name : '暂时没有可加入的群' }}
        </h2>
        <p>{{ group.message }}</p>
        <div v-if="group.available" class="text-body-2 muted mb-6">
          群号 {{ group.group_id }} · 成员 {{ group.current_members }} /
          {{ group.max_members || '不限' }}
        </div>
        <v-btn
          v-if="group.available && group.join_url"
          :href="group.join_url"
          target="_blank"
          rel="noopener noreferrer"
          block
          size="large"
          :append-icon="mdiOpenInNew"
        >
          申请加入
        </v-btn>
      </template>
      <v-btn variant="text" block class="mt-4" :loading="loading" @click="load">刷新推荐</v-btn>
    </v-card>
  </main>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { mdiAccountGroupOutline, mdiOpenInNew } from '@mdi/js'
import { api } from '../api/client'
import QueryError from '../components/QueryError.vue'
type PublicGroup = {
  available: boolean
  group_id?: number
  group_name?: string
  join_url?: string
  current_members?: number
  max_members?: number
  message: string
}
const group = ref<PublicGroup | null>(null),
  error = ref<unknown>(null),
  loading = ref(false)
async function load() {
  loading.value = true
  error.value = null
  try {
    group.value = (await api.get<PublicGroup>('/public/recommended-group')).data
  } catch (failure) {
    error.value = failure
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
