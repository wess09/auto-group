import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { createVuetify } from 'vuetify'
import { md3 } from 'vuetify/blueprints'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import { zhHans } from 'vuetify/locale'
import 'vuetify/styles'
import '@fontsource/roboto/latin-400.css'
import '@fontsource/roboto/latin-500.css'
import '@fontsource/roboto/latin-700.css'
import './styles/app.css'
import App from './App.vue'
import router from './routers'
import pinia from './stores'
import { queryClient } from './api/queries'
import { createMaterialTheme } from './theme/dynamicTheme'

const vuetify = createVuetify({
  blueprint: md3,
  icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
  locale: { locale: 'zhHans', messages: { zhHans } },
  theme: {
    defaultTheme: 'light',
    themes: { light: createMaterialTheme(false), dark: createMaterialTheme(true) },
  },
  defaults: {
    VCard: { elevation: 0 },
    VTextField: { variant: 'outlined' },
    VSelect: { variant: 'outlined' },
    VTextarea: { variant: 'outlined' },
  },
})
createApp(App)
  .use(pinia)
  .use(vuetify)
  .use(VueQueryPlugin, { queryClient })
  .use(router)
  .mount('#app')
