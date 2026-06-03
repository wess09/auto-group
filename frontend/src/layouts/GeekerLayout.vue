<template>
  <div class="geeker-layout" :class="{ 'is-collapsed': collapsed }">
    <aside class="geeker-sider">
      <RouterLink class="geeker-logo" :to="adminBase">
        <span class="geeker-logo-mark">A</span>
        <strong v-show="!collapsed">Auto Group</strong>
      </RouterLink>
      <el-scrollbar class="geeker-menu-scroll">
        <el-menu
          :default-active="activePath"
          :collapse="collapsed"
          :collapse-transition="false"
          router
          class="geeker-menu"
        >
          <el-menu-item v-for="item in adminMenuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-menu>
      </el-scrollbar>
    </aside>

    <section class="geeker-container">
      <header class="geeker-header">
        <div class="geeker-header-left">
          <el-button text class="icon-button" @click="collapsed = !collapsed">
            <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>Auto Group</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="geeker-header-actions">
          <el-button text @click="goPublic">
            <el-icon><Link /></el-icon>
            公开入口
          </el-button>
          <el-button type="primary" plain @click="logout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-button>
        </div>
      </header>

      <div class="geeker-tabs">
        <el-scrollbar>
          <div class="geeker-tabs-inner">
            <RouterLink
              v-for="tab in tabs"
              :key="tab.path"
              class="geeker-tab"
              :class="{ active: tab.path === activePath }"
              :to="tab.path"
            >
              <span>{{ tab.title }}</span>
              <el-icon v-if="!tab.affix" @click.prevent.stop="closeTab(tab.path)">
                <Close />
              </el-icon>
            </RouterLink>
          </div>
        </el-scrollbar>
      </div>

      <main class="geeker-main">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Close, Expand, Fold, Link, SwitchButton } from '@element-plus/icons-vue'
import { adminBase, adminPath } from '../adminRoute'
import { adminMenuItems, titleByPath } from '../routers/adminMenu'
import { useTabsStore } from '../stores/modules/tabs'
import { useUserStore } from '../stores/modules/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const tabsStore = useTabsStore()
const collapsed = ref(false)

const activePath = computed(() => route.path)
const currentTitle = computed(() => String(route.meta.title || titleByPath(route.path)))
const tabs = computed(() => tabsStore.tabs)

function closeTab(path: string) {
  tabsStore.removeTab(path)
  if (path === route.path) {
    const next = tabs.value[tabs.value.length - 1]
    router.push(next?.path || adminBase)
  }
}

function goPublic() {
  router.push('/join')
}

function logout() {
  userStore.clearToken()
  router.push(adminPath('login'))
}
</script>
