<template>
  <v-navigation-drawer
    v-model="drawer"
    :permanent="!mobile"
    :temporary="mobile"
    :rail="rail"
    color="surface-container"
  >
    <v-list-item
      title="Auto Group"
      subtitle="群管理工作台"
      :prepend-icon="mdiHexagonMultipleOutline"
      class="my-4"
    />
    <v-divider />
    <v-list nav class="pa-3">
      <v-list-item
        v-for="item in adminMenuItems"
        :key="item.path"
        :to="item.path"
        :title="item.title"
        :aria-label="item.title"
        :prepend-icon="item.icon"
        :active="route.path === item.path"
        color="primary"
        rounded="xl"
        @click="mobile && (drawer = false)"
      />
    </v-list>
  </v-navigation-drawer>
  <v-app-bar flat color="surface-container-low" height="64">
    <v-btn v-if="mobile" :icon="mdiMenu" aria-label="打开导航" @click="drawer = !drawer" />
    <v-app-bar-title class="text-body-1">{{ titleByPath(route.path) }}</v-app-bar-title>
    <v-chip
      size="small"
      :color="socket.status.value === 'connected' ? 'primary' : 'warning'"
      class="mr-2"
    >
      {{ connectionLabel }}
    </v-chip>
    <v-menu>
      <template #activator="{ props }">
        <v-btn v-bind="props" :icon="mdiThemeLightDark" aria-label="切换主题" />
      </template>
      <v-list>
        <v-list-item
          v-for="item in modes"
          :key="item.value"
          :title="item.title"
          :active="themeMode === item.value"
          @click="themeMode = item.value"
        />
      </v-list>
    </v-menu>
    <v-btn :icon="mdiLogout" aria-label="退出登录" @click="logout" />
    <template #extension>
      <v-tabs
        :model-value="route.path"
        color="primary"
        density="compact"
        show-arrows
        class="flex-grow-1"
      >
        <v-tab v-for="tab in tabsStore.tabs" :key="tab.path" :value="tab.path" :to="tab.path">
          {{ tab.title }}
        </v-tab>
      </v-tabs>
      <v-btn
        :icon="mdiClose"
        variant="text"
        size="small"
        aria-label="关闭当前页面标签"
        :disabled="route.path === adminBase"
        @click="closeCurrent"
      />
    </template>
  </v-app-bar>
  <v-main><router-view :key="route.path" /></v-main>
</template>
<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { useRoute, useRouter } from 'vue-router'
import { mdiMenu, mdiThemeLightDark, mdiLogout, mdiClose, mdiHexagonMultipleOutline } from '@mdi/js'
import { adminBase, adminPath } from '../adminRoute'
import { adminMenuItems, titleByPath } from '../routers/adminMenu'
import { useTabsStore } from '../stores/modules/tabs'
import { useUserStore } from '../stores/modules/user'
import { themeMode, type ThemeMode } from '../theme/dynamicTheme'
import { socket } from '../api/client'
import { queryClient } from '../api/queries'
import { pageStates, report } from '../stores/ui'
const route = useRoute(),
  router = useRouter(),
  tabsStore = useTabsStore(),
  userStore = useUserStore()
const { width } = useDisplay()
const mobile = computed(() => width.value < 600),
  rail = computed(() => width.value >= 600 && width.value < 1200)
const drawer = ref(!mobile.value)
watch(mobile, (value) => {
  drawer.value = !value
})
const connectionLabel = computed(
  () =>
    ({ connected: '已连接', connecting: '连接中', reconnecting: '重连中', disconnected: '已断线' })[
      socket.status.value
    ],
)
const modes: { value: ThemeMode; title: string }[] = [
  { value: 'system', title: '跟随系统' },
  { value: 'light', title: '浅色' },
  { value: 'dark', title: '深色' },
]
function logout() {
  socket.close()
  queryClient.clear()
  pageStates.clear()
  tabsStore.tabs = []
  userStore.clearToken()
  void router.push(adminPath('login'))
}
function closeCurrent() {
  const index = tabsStore.tabs.findIndex((tab) => tab.path === route.path)
  const path = route.path
  tabsStore.removeTab(path)
  pageStates.delete(path)
  void router.push(tabsStore.tabs[Math.max(0, index - 1)]?.path || adminBase)
}
onMounted(() => {
  void socket.connect().catch(report)
})
onBeforeUnmount(() => {
  socket.close()
})
</script>
