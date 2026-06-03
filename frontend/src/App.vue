<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { fallbackDynamicTheme, themeFromBackgroundImage } from './theme/dynamicTheme'

onMounted(async () => {
  fallbackDynamicTheme()
  await themeFromBackgroundImage()
})
</script>
