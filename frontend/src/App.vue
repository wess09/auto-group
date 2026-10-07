<template>
  <v-app>
    <router-view />
    <v-snackbar v-model="toast.open" :color="toast.color" :timeout="5000">
      {{ toast.text }}
      <template #actions><v-btn variant="text" @click="toast.open = false">关闭</v-btn></template>
    </v-snackbar>
  </v-app>
</template>
<script setup lang="ts">
import { watchEffect } from 'vue'
import { useTheme } from 'vuetify'
import { systemDark, themeMode } from './theme/dynamicTheme'
import { toast } from './stores/ui'
const theme = useTheme()
watchEffect(() => {
  localStorage.setItem('md3.theme_mode', themeMode.value)
  void theme.change(
    themeMode.value === 'system' ? (systemDark.value ? 'dark' : 'light') : themeMode.value,
  )
})
</script>
