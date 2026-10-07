<template>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4" role="alert">
    {{ error instanceof Error ? error.message : '加载失败' }}
    <v-btn variant="text" class="ml-3" @click="$emit('retry')">重试</v-btn>
  </v-alert>
</template>
<script setup lang="ts">
defineProps<{ error: unknown }>()
defineEmits<{ retry: [] }>()
</script>
