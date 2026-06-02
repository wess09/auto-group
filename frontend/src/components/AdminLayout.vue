<template>
  <n-layout has-sider class="admin-shell">
    <n-layout-sider
      class="admin-sider"
      bordered
      collapse-mode="width"
      :collapsed-width="0"
      :width="224"
      show-trigger="bar"
    >
      <div class="brand">
        <div class="brand-mark">A</div>
        <span>Auto Group</span>
      </div>
      <n-menu :value="route.path" :options="menuOptions" @update:value="go" />
    </n-layout-sider>
    <n-layout-content>
      <main class="admin-main">
        <slot />
      </main>
    </n-layout-content>
  </n-layout>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { NIcon, type MenuOption } from 'naive-ui'
import { adminBase, adminPath } from '../adminRoute'
import {
  Bell,
  ClipboardCheck,
  Dashboard,
  Files,
  GitMerge,
  Login,
  Logout,
  MessageCircle,
  Settings,
  Users
} from '@vicons/tabler'

const route = useRoute()
const router = useRouter()

function icon(component: unknown) {
  return () => h(NIcon, null, { default: () => h(component as never) })
}

const menuOptions: MenuOption[] = [
  { label: () => h(RouterLink, { to: adminBase }, { default: () => '仪表盘' }), key: adminBase, icon: icon(Dashboard) },
  { label: () => h(RouterLink, { to: adminPath('groups') }, { default: () => '群配置' }), key: adminPath('groups'), icon: icon(Users) },
  { label: () => h(RouterLink, { to: adminPath('rules') }, { default: () => '入群规则' }), key: adminPath('rules'), icon: icon(ClipboardCheck) },
  { label: () => h(RouterLink, { to: adminPath('notices') }, { default: () => '公告管理' }), key: adminPath('notices'), icon: icon(Bell) },
  { label: () => h(RouterLink, { to: adminPath('files') }, { default: () => '群文件' }), key: adminPath('files'), icon: icon(Files) },
  { label: () => h(RouterLink, { to: adminPath('essence') }, { default: () => '精华管理' }), key: adminPath('essence'), icon: icon(MessageCircle) },
  { label: () => h(RouterLink, { to: adminPath('dedupe') }, { default: () => '一键去重' }), key: adminPath('dedupe'), icon: icon(GitMerge) },
  { label: () => h(RouterLink, { to: adminPath('events') }, { default: () => '事件日志' }), key: adminPath('events'), icon: icon(Settings) },
  { label: () => h(RouterLink, { to: '/join' }, { default: () => '公开入口' }), key: '/join', icon: icon(Login) },
  { label: '退出登录', key: 'logout', icon: icon(Logout) }
]

function go(key: string) {
  if (key === 'logout') {
    localStorage.removeItem('token')
    router.push(adminPath('login'))
    return
  }
  router.push(key)
}
</script>
