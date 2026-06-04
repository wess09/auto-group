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
          <el-menu-item
            v-for="item in adminMenuItems"
            :key="item.path"
            :index="item.path"
            :style="collapsed ? {
              padding: '0px',
              width: '48px',
              height: '46px',
              lineHeight: '46px',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              margin: '4px 12px'
            } : {}"
          >
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
        <div class="geeker-header-actions" style="gap: 8px">
          <el-tooltip content="公开入口" placement="bottom">
            <el-button type="info" link :icon="Link" class="header-action-btn" @click="goPublic" />
          </el-tooltip>
          <el-tooltip content="退出登录" placement="bottom">
            <el-button type="danger" link :icon="SwitchButton" class="header-action-btn" @click="logout" />
          </el-tooltip>
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

<style scoped>
.header-action-btn {
  font-size: 20px !important;
  width: 36px !important;
  height: 36px !important;
  padding: 0 !important;
  border-radius: 8px !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  transition: all 0.2s ease !important;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
}
.header-action-btn:hover {
  background-color: #f1f5f9 !important;
  transform: scale(1.1) !important;
}
.header-action-btn:active {
  transform: scale(0.95) !important;
}
.el-button.header-action-btn.el-button--info {
  color: var(--geeker-text-secondary) !important;
}
.el-button.header-action-btn.el-button--info:hover {
  color: var(--md-primary) !important;
}
.el-button.header-action-btn.el-button--danger {
  color: var(--el-color-danger) !important;
}
</style>
