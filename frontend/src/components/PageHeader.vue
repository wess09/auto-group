<template>
  <div class="page-header">
    <div>
      <h1>{{ title }}</h1>
      <p v-if="subtitle">{{ subtitle }}</p>
    </div>
    <div class="d-flex ga-2"><slot /></div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>
