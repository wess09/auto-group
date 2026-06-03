<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <router-view />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { GlobalThemeOverrides } from 'naive-ui'
import { fallbackDynamicTheme, themeFromBackgroundImage } from './theme/dynamicTheme'

const themeOverrides = ref<GlobalThemeOverrides>(fallbackDynamicTheme().naive)

onMounted(async () => {
  themeOverrides.value = (await themeFromBackgroundImage()).naive
})
</script>
