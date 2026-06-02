import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
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
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/admin' },
    { path: '/join', component: JoinView },
    { path: '/login', component: LoginView },
    { path: '/admin', component: DashboardView },
    { path: '/admin/groups', component: GroupsView },
    { path: '/admin/rules', component: RulesView },
    { path: '/admin/notices', component: NoticesView },
    { path: '/admin/files', component: FilesView },
    { path: '/admin/essence', component: EssenceView },
    { path: '/admin/dedupe', component: DedupeView },
    { path: '/admin/events', component: EventsView }
  ]
})

router.beforeEach((to) => {
  if (to.path.startsWith('/admin') && !localStorage.getItem('token')) {
    return '/login'
  }
  if (to.path === '/login' && localStorage.getItem('token')) {
    return '/admin'
  }
})

createApp(App)
  .provide('darkTheme', darkTheme)
  .use(router)
  .use(naive)
  .mount('#app')
