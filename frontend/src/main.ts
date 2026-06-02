import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import {
  create,
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NConfigProvider,
  NDataTable,
  NDivider,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NIcon,
  NInput,
  NInputNumber,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NMenu,
  NMessageProvider,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NUpload,
  darkTheme
} from 'naive-ui'
import App from './App.vue'
import DashboardView from './views/DashboardView.vue'
import DedupeView from './views/DedupeView.vue'
import EssenceView from './views/EssenceView.vue'
import EventsView from './views/EventsView.vue'
import FilesView from './views/FilesView.vue'
import GroupsView from './views/GroupsView.vue'
import JoinView from './views/JoinView.vue'
import LoginView from './views/LoginView.vue'
import NoticesView from './views/NoticesView.vue'
import RulesView from './views/RulesView.vue'
import { adminBase, adminPath, isAdminPath, isLoginPath } from './adminRoute'
import './styles/app.css'

const naive = create({
  components: [
    NAlert,
    NButton,
    NCard,
    NCheckbox,
    NCheckboxGroup,
    NConfigProvider,
    NDataTable,
    NDivider,
    NForm,
    NFormItem,
    NGrid,
    NGridItem,
    NIcon,
    NInput,
    NInputNumber,
    NLayout,
    NLayoutContent,
    NLayoutSider,
    NMenu,
    NMessageProvider,
    NModal,
    NPopconfirm,
    NSelect,
    NSpace,
    NSpin,
    NSwitch,
    NTag,
    NUpload
  ]
})

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/join' },
    { path: '/join', component: JoinView },
    { path: adminPath('login'), component: LoginView },
    { path: adminBase, component: DashboardView },
    { path: adminPath('groups'), component: GroupsView },
    { path: adminPath('rules'), component: RulesView },
    { path: adminPath('notices'), component: NoticesView },
    { path: adminPath('files'), component: FilesView },
    { path: adminPath('essence'), component: EssenceView },
    { path: adminPath('dedupe'), component: DedupeView },
    { path: adminPath('events'), component: EventsView }
  ]
})

router.beforeEach((to) => {
  if (isAdminPath(to.path) && !isLoginPath(to.path) && !localStorage.getItem('token')) {
    return adminPath('login')
  }
  if (isLoginPath(to.path) && localStorage.getItem('token')) {
    return adminBase
  }
})

createApp(App)
  .provide('darkTheme', darkTheme)
  .use(router)
  .use(naive)
  .mount('#app')
