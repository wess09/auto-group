import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { adminBase, adminPath, isAdminPath, isLoginPath } from '../adminRoute'
import GeekerLayout from '../layouts/GeekerLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import DedupeView from '../views/DedupeView.vue'
import EssenceView from '../views/EssenceView.vue'
import EventsView from '../views/EventsView.vue'
import FilesView from '../views/FilesView.vue'
import GroupsView from '../views/GroupsView.vue'
import JoinBlacklistView from '../views/JoinBlacklistView.vue'
import JoinView from '../views/JoinView.vue'
import LoginView from '../views/LoginView.vue'
import MessageModerationView from '../views/MessageModerationView.vue'
import NoticesView from '../views/NoticesView.vue'
import RulesView from '../views/RulesView.vue'
import { titleByPath } from './adminMenu'
import { useTabsStore } from '../stores/modules/tabs'
import { useUserStore } from '../stores/modules/user'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/join' },
  { path: '/join', name: 'join', component: JoinView, meta: { title: '公开入口' } },
  { path: adminPath('login'), name: 'login', component: LoginView, meta: { title: '后台登录' } },
  {
    path: adminBase,
    component: GeekerLayout,
    children: [
      { path: '', name: 'dashboard', component: DashboardView, meta: { title: '仪表盘', affix: true } },
      { path: 'groups', name: 'groups', component: GroupsView, meta: { title: '群配置' } },
      { path: 'rules', name: 'rules', component: RulesView, meta: { title: '入群规则' } },
      { path: 'join-blacklist', name: 'joinBlacklist', component: JoinBlacklistView, meta: { title: '加群黑名单' } },
      { path: 'message-moderation', name: 'messageModeration', component: MessageModerationView, meta: { title: '消息审查' } },
      { path: 'notices', name: 'notices', component: NoticesView, meta: { title: '公告管理' } },
      { path: 'files', name: 'files', component: FilesView, meta: { title: '群文件' } },
      { path: 'essence', name: 'essence', component: EssenceView, meta: { title: '精华管理' } },
      { path: 'dedupe', name: 'dedupe', component: DedupeView, meta: { title: '一键去重' } },
      { path: 'events', name: 'events', component: EventsView, meta: { title: '事件日志' } }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ left: 0, top: 0 })
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (isAdminPath(to.path) && !isLoginPath(to.path) && !userStore.token) {
    return adminPath('login')
  }
  if (isLoginPath(to.path) && userStore.token) {
    return adminBase
  }
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || titleByPath(to.path))} - Auto Group`
  if (isAdminPath(to.path) && !isLoginPath(to.path)) {
    useTabsStore().addTab({
      path: to.path,
      title: String(to.meta.title || titleByPath(to.path)),
      affix: Boolean(to.meta.affix)
    })
  }
})

export default router
