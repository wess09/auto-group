<template>
  <section class="join-page">
    <div class="join-panel">
      <n-spin :show="loading">
        <h1 class="join-title">自动群分流</h1>
        <template v-if="group?.available">
          <p class="join-meta">{{ group.message }}</p>
          <div class="metric">
            <div class="metric-label">推荐群</div>
            <div class="metric-value">{{ group.group_name }}</div>
          </div>
          <p class="join-meta">
            当前人数 {{ group.current_members ?? 0 }}
            <span v-if="group.max_members">/ {{ group.max_members }}</span>
          </p>
          <n-button type="primary" size="large" block tag="a" :href="group.join_url" target="_blank">
            打开入群链接
          </n-button>
        </template>
        <n-alert v-else type="warning" :bordered="false">
          {{ group?.message || '当前没有可加入的群' }}
        </n-alert>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const loading = ref(true)
const group = ref<any>(null)

onMounted(async () => {
  try {
    const { data } = await api.get('/public/recommended-group')
    group.value = data
  } finally {
    loading.value = false
  }
})
</script>
