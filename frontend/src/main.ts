import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import * as Icons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './routers'
import pinia from './stores'
import 'element-plus/dist/index.css'
import './styles/app.css'

const app = createApp(App)

Object.entries(Icons).forEach(([key, component]) => {
  app.component(key, component)
})

app
  .use(pinia)
  .use(ElementPlus)
  .use(router)
  .mount('#app')
